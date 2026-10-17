import tempfile
import zipfile
from datetime import date
from pathlib import Path

import shapefile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from soil_analysis.domain.service.municipality_boundary_import import (
    MunicipalityBoundaryImportService,
)
from soil_analysis.domain.service.municipality_soil_aggregation import (
    MunicipalitySoilAggregationService,
)
from soil_analysis.models import (
    MunicipalityBoundary,
    MunicipalityBoundaryDataset,
    MunicipalitySoilAggregation,
    SoilMapDataset,
    SoilMapPolygon,
)


class MunicipalityBoundaryImportServiceTest(TestCase):
    def test_import_boundary_from_zip_stores_all_municipalities_and_activates_dataset(
        self,
    ):
        """
        シナリオ:
        - 入力: N03_001、N03_004、N03_007とJGD_2011を持つ全国行政区域Shape ZIP。
        - 処理: MunicipalityBoundaryImportServiceでZIPを取り込む。
        - 期待値: 47都道府県の市区町村境界を保存し、新しいデータ版が有効になること。
        """
        with tempfile.TemporaryDirectory() as directory:
            dataset = MunicipalityBoundaryImportService.import_boundary_from_zip(
                self._create_boundary_zip(Path(directory))
            )

        self.assertTrue(dataset.is_active)
        self.assertEqual(dataset.source_date, date(2024, 1, 1))
        self.assertEqual(dataset.municipality_count, 47)
        self.assertEqual(dataset.feature_count, 47)
        self.assertEqual(dataset.municipalities.count(), 47)
        self.assertEqual(
            dataset.municipalities.get(municipality_code="02001").name, "青森市"
        )

    def test_import_boundary_from_zip_uses_municipality_shape_when_prefecture_shape_is_also_included(
        self,
    ):
        """
        シナリオ:
        - 入力: 市区町村境界Shapeと都道府県境界Shapeを同梱した国土数値情報N03の全国ZIP。
        - 処理: MunicipalityBoundaryImportServiceでZIPを取り込む。
        - 期待値: N03_007を持つ市区町村境界Shapeだけを選び、全国の市区町村境界を保存すること。
        """
        with tempfile.TemporaryDirectory() as directory:
            dataset = MunicipalityBoundaryImportService.import_boundary_from_zip(
                self._create_boundary_zip(
                    Path(directory), include_prefecture_shape=True
                )
            )

        self.assertEqual(dataset.municipality_count, 47)
        self.assertEqual(dataset.feature_count, 47)
        self.assertEqual(
            dataset.municipalities.get(municipality_code="02001").name, "青森市"
        )

    @staticmethod
    def _create_boundary_zip(
        directory: Path, include_prefecture_shape: bool = False
    ) -> Path:
        shape_path = directory / "municipality.shp"
        writer = shapefile.Writer(str(shape_path), encoding="utf-8")
        writer.field("N03_001", "C", size=40)
        writer.field("N03_004", "C", size=80)
        writer.field("N03_007", "C", size=5)
        for prefecture_code in range(1, 48):
            lng = 100 + prefecture_code
            writer.poly([_square(lng, 30, lng + 0.5, 30.5)])
            municipality_name = (
                "青森市" if prefecture_code == 2 else f"市区町村{prefecture_code}"
            )
            writer.record("都道府県", municipality_name, f"{prefecture_code:02d}001")
        writer.close()
        shape_path.with_suffix(".prj").write_text("GCS_JGD_2011", encoding="utf-8")
        shape_path.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
        zip_path = directory / "N03-20240101_GML.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                zip_file.write(shape_path.with_suffix(suffix), f"municipality{suffix}")
            if include_prefecture_shape:
                prefecture_shape_path = directory / "municipality_prefecture.shp"
                prefecture_writer = shapefile.Writer(
                    str(prefecture_shape_path), encoding="utf-8"
                )
                prefecture_writer.field("N03_001", "C", size=40)
                prefecture_writer.field("N03_004", "C", size=80)
                prefecture_writer.field("N03_007", "C", size=5)
                prefecture_writer.poly([_square(140, 30, 141, 31)])
                prefecture_writer.record("都道府県", "都道府県", "01000")
                prefecture_writer.close()
                prefecture_shape_path.with_suffix(".prj").write_text(
                    "GCS_JGD_2011", encoding="utf-8"
                )
                prefecture_shape_path.with_suffix(".cpg").write_text(
                    "UTF-8", encoding="ascii"
                )
                for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                    zip_file.write(
                        prefecture_shape_path.with_suffix(suffix),
                        f"municipality_prefecture{suffix}",
                    )
        return zip_path


class MunicipalitySoilAggregationServiceTest(TestCase):
    def setUp(self):
        self.soil_dataset = SoilMapDataset.objects.create(
            source_file_name="全国_20.zip",
            source_sha256="a" * 64,
            source_crs="GCS_JGD_2000",
            feature_count=48,
            is_active=True,
            imported_at=timezone.now(),
        )
        self.boundary_dataset = MunicipalityBoundaryDataset.objects.create(
            source_file_name="N03-20240101_GML.zip",
            source_sha256="b" * 64,
            source_crs="GCS_JGD_2011",
            source_date=date(2024, 1, 1),
            feature_count=48,
            municipality_count=48,
            is_active=True,
            imported_at=timezone.now(),
        )
        self._create_national_test_data()

    def test_recalculate_stores_intersection_areas_and_classification_hierarchy(self):
        """
        シナリオ:
        - 入力: 全国47都道府県の境界と土壌図、青森県内を二つに分けた土壌Polygon。
        - 処理: 市区町村別の交差面積を再計算する。
        - 期待値: 全市区町村の集計と、土壌群から土壌名までの面積内訳が保存されること。
        """
        municipality_count = (
            MunicipalitySoilAggregationService.recalculate_active_datasets()
        )

        aggregation = MunicipalitySoilAggregation.objects.get(
            municipality__municipality_code="02201"
        )
        soil_area = aggregation.soil_areas.get(soil_name="黒ボク土")
        self.assertEqual(municipality_count, 48)
        self.assertGreater(aggregation.classified_area_sq_m, 0)
        self.assertAlmostEqual(
            aggregation.classified_area_sq_m,
            aggregation.municipality_area_sq_m,
            delta=1,
        )
        self.assertAlmostEqual(
            soil_area.area_sq_m, aggregation.classified_area_sq_m, delta=1
        )
        self.assertEqual(soil_area.soil_group_code, "A")
        self.assertEqual(soil_area.soil_subgroup_code, "A1")
        self.assertEqual(soil_area.soil_series_code, "A11")

    def test_prefecture_detail_tab_and_municipality_page_display_soil_aggregation(
        self,
    ):
        """
        シナリオ:
        - 入力: 再計算済みの青森市土壌面積と、ホームの地図表示。
        - 処理: ホーム、都道府県詳細、市区町村詳細と旧土壌都道府県URLをGETする。
        - 期待値: ホームは天気・商圏だけを表示し、共通詳細の土壌分析タブから市区町村と分類別構成比を確認でき、削除済みの旧URLは404になること。
        """
        MunicipalitySoilAggregationService.recalculate_active_datasets()

        home_response = self.client.get(reverse("soil:home"))
        prefecture_response = self.client.get(
            reverse("soil:prefecture_detail", kwargs={"prefecture_id": 2})
        )
        legacy_response = self.client.get("/soil_analysis/soil-map/prefecture/2")
        municipality_response = self.client.get(
            reverse(
                "soil:soil_map_municipality",
                kwargs={"municipality_code": "02201"},
            )
        )

        self.assertContains(home_response, "日本地図の天気・商圏")
        self.assertNotContains(home_response, "soil-map-mode")
        self.assertNotContains(home_response, "data-soil-detail-url-template")
        self.assertContains(prefecture_response, "地域分析")
        self.assertContains(prefecture_response, "土壌分析")
        self.assertContains(prefecture_response, "青森市")
        self.assertContains(
            prefecture_response,
            reverse(
                "soil:soil_map_municipality", kwargs={"municipality_code": "02201"}
            ),
        )
        self.assertEqual(legacy_response.status_code, 404)
        self.assertContains(municipality_response, "主な土壌タイプ")
        self.assertContains(municipality_response, "構成比 ▼")
        self.assertContains(municipality_response, "黒ボク土")
        self.assertContains(municipality_response, "構成比")
        self.assertContains(
            municipality_response,
            f"{reverse('soil:prefecture_detail', kwargs={'prefecture_id': 2})}#soil-analysis",
        )

    def _create_national_test_data(self):
        for prefecture_code in range(1, 48):
            code = f"{prefecture_code:02d}"
            lng = 100 + prefecture_code
            if prefecture_code == 2:
                self._create_boundary("02201", "青森市", 140, 30, 140.5, 30.5)
                self._create_boundary("02202", "弘前市", 140.5, 30, 141, 30.5)
                self._create_soil_polygon(
                    code, "A", "A1", "A11", "黒ボク土", 140, 30, 140.5, 30.5
                )
                self._create_soil_polygon(
                    code, "B", "B1", "B11", "褐色森林土", 140.5, 30, 141, 30.5
                )
                continue
            self._create_boundary(
                f"{code}001", f"市区町村{prefecture_code}", lng, 30, lng + 0.5, 30.5
            )
            self._create_soil_polygon(
                code, "C", "C1", "C11", "土壌", lng, 30, lng + 0.5, 30.5
            )

    def _create_boundary(self, code, name, min_lng, min_lat, max_lng, max_lat):
        MunicipalityBoundary.objects.create(
            dataset=self.boundary_dataset,
            prefecture_code=code[:2],
            municipality_code=code,
            name=name,
            coordinates=[[_square(min_lng, min_lat, max_lng, max_lat)]],
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )

    def _create_soil_polygon(
        self,
        prefecture_code,
        group_code,
        subgroup_code,
        series_code,
        soil_name,
        min_lng,
        min_lat,
        max_lng,
        max_lat,
    ):
        SoilMapPolygon.objects.create(
            dataset=self.soil_dataset,
            prefecture_code=prefecture_code,
            soil_group_code=group_code,
            soil_subgroup_code=subgroup_code,
            soil_series_code=series_code,
            soil_name=soil_name,
            coordinates=[_square(min_lng, min_lat, max_lng, max_lat)],
            min_lng=min_lng,
            min_lat=min_lat,
            max_lng=max_lng,
            max_lat=max_lat,
        )


def _square(min_lng, min_lat, max_lng, max_lat):
    return [
        [min_lng, min_lat],
        [min_lng, max_lat],
        [max_lng, max_lat],
        [max_lng, min_lat],
        [min_lng, min_lat],
    ]
