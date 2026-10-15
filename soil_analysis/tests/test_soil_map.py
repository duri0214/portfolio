import tempfile
import zipfile
from pathlib import Path

import shapefile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.domain.service.soil_map import SoilMapService
from soil_analysis.domain.service.soil_map_import import (
    SoilMapImportError,
    SoilMapImportService,
)
from soil_analysis.models import SoilMapDataset, SoilMapPolygon


class SoilMapImportServiceTest(TestCase):
    def test_import_zip_file_stores_all_polygons_and_activates_the_new_dataset(self):
        """
        シナリオ:
        - 入力: JGD_2000・必須属性を含む全国土壌図形式のZIP。
        - 処理: SoilMapImportServiceでZIPを取り込む。
        - 期待値: Polygonを保存し、新しいデータ版だけが有効になること。
        """
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_zip_file(
                Path(directory),
                dbf_encoding="cp932",
                include_cpg=False,
                include_empty_record=True,
            )

            dataset = SoilMapImportService.import_zip_file(zip_path)

        self.assertTrue(dataset.is_active)
        self.assertEqual(dataset.feature_count, 49)
        self.assertEqual(dataset.excluded_feature_count, 1)
        self.assertEqual(SoilMapPolygon.objects.filter(dataset=dataset).count(), 49)
        self.assertEqual(SoilMapPolygon.objects.first().prefecture_code, "02")

    def test_prefecture_zip_is_rejected_before_it_creates_a_dataset(self):
        """
        シナリオ:
        - 入力: 全国47都道府県を含まないShape ZIP。
        - 処理: SoilMapImportServiceでZIPを取り込む。
        - 期待値: データ版とPolygonを保存せず、取込エラーになること。
        """
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_zip_file(
                Path(directory), include_national_coverage=False
            )

            with self.assertRaisesRegex(SoilMapImportError, "全国版"):
                SoilMapImportService.import_zip_file(zip_path)

        self.assertEqual(SoilMapDataset.objects.count(), 0)
        self.assertEqual(SoilMapPolygon.objects.count(), 0)

    def test_invalid_zip_file_keeps_the_current_dataset_active(self):
        """
        シナリオ:
        - 入力: 既に有効なデータ版と、座標系が異なるZIP。
        - 処理: 不正なZIPを取り込む。
        - 期待値: 取込エラーとなり、既存の有効版が維持されること。
        """
        current = SoilMapDataset.objects.create(
            source_file_name="current.zip",
            source_sha256="0" * 64,
            source_crs="JGD_2000",
            feature_count=1,
            is_active=True,
            imported_at="2026-01-01T00:00:00+09:00",
        )
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_zip_file(Path(directory), crs="WGS_1984")

            with self.assertRaises(SoilMapImportError):
                SoilMapImportService.import_zip_file(zip_path)

        current.refresh_from_db()
        self.assertTrue(current.is_active)
        self.assertEqual(SoilMapDataset.objects.filter(is_active=True).count(), 1)

    def test_zip_slip_path_is_rejected_before_it_creates_a_dataset(self):
        """
        シナリオ:
        - 入力: Shapeファイルと、展開先の親ディレクトリを指すパスを含むZIP。
        - 処理: SoilMapImportServiceでZIPを取り込む。
        - 期待値: データ版とPolygonを保存せず、取込エラーになること。
        """
        with tempfile.TemporaryDirectory() as directory:
            zip_path = self._create_zip_file(Path(directory))
            with zipfile.ZipFile(zip_path, "a") as zip_file:
                zip_file.writestr("../outside.txt", "unsafe")

            with self.assertRaisesRegex(SoilMapImportError, "展開できないパス"):
                SoilMapImportService.import_zip_file(zip_path)

        self.assertEqual(SoilMapDataset.objects.count(), 0)
        self.assertEqual(SoilMapPolygon.objects.count(), 0)

    @staticmethod
    def _create_zip_file(
        directory: Path,
        crs: str = "GCS_JGD_2000",
        dbf_encoding: str = "utf-8",
        include_cpg: bool = True,
        include_empty_record: bool = False,
        include_national_coverage: bool = True,
    ) -> Path:
        shape_path = directory / "national.shp"
        writer = shapefile.Writer(str(shape_path), encoding=dbf_encoding)
        writer.field("Pref_JCD", "C")
        writer.field("SG_CD", "C")
        writer.field("SSbG_CD", "C")
        writer.field("SSerGrCD", "C")
        writer.field("SoilName", "C", size=100)
        writer.poly([[[140.7, 40.7], [140.8, 40.7], [140.8, 40.8], [140.7, 40.7]]])
        writer.record("02", "A", "A1", "A11", "黒ボク土")
        writer.poly([[[140.8, 40.7], [140.9, 40.7], [140.9, 40.8], [140.8, 40.7]]])
        writer.record("02", "A", "A1", "A11", "黒ボク土")
        writer.poly([[[140.9, 40.7], [141.0, 40.7], [141.0, 40.8], [140.9, 40.7]]])
        writer.record("02", "B", "B1", "B11", "褐色森林土")
        if include_empty_record:
            writer.poly(
                [
                    [
                        [133.5, 33.7],
                        [133.6, 33.7],
                        [133.6, 33.8],
                        [133.5, 33.7],
                    ]
                ]
            )
            writer.record("39", "", "", "", "")
        if include_national_coverage:
            for prefecture_code in range(1, 48):
                if prefecture_code == 2:
                    continue
                writer.poly(
                    [
                        [
                            [140.0, 35.0],
                            [140.1, 35.0],
                            [140.1, 35.1],
                            [140.0, 35.0],
                        ]
                    ]
                )
                writer.record(f"{prefecture_code:02d}", "C", "C1", "C11", "soil")
        writer.close()
        shape_path.with_suffix(".prj").write_text(crs, encoding="utf-8")
        if include_cpg:
            shape_path.with_suffix(".cpg").write_text(
                dbf_encoding.upper(), encoding="ascii"
            )
        zip_path = directory / "national.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                member_path = shape_path.with_suffix(suffix)
                if member_path.is_file():
                    zip_file.write(member_path, f"national{suffix}")
        return zip_path


class SoilMapServiceTest(TestCase):
    def test_build_payload_returns_dominant_soil_for_each_prefecture(self):
        """
        シナリオ:
        - 入力: 青森県に黒ボク土2件、褐色森林土1件を持つ有効データ版。
        - 処理: SoilMapServiceで地図用payloadを作る。
        - 期待値: 青森県の代表土壌として黒ボク土と合計3件を返すこと。
        """
        with tempfile.TemporaryDirectory() as directory:
            SoilMapImportService.import_zip_file(
                SoilMapImportServiceTest._create_zip_file(Path(directory))
            )

        payload = SoilMapService.build_payload()
        aomori = next(area for area in payload["areas"] if area["code"] == 2)

        self.assertEqual(aomori["soilName"], "黒ボク土")
        self.assertEqual(aomori["polygonCount"], 3)
        self.assertEqual(aomori["dominantPolygonCount"], 2)
        self.assertEqual(payload["dataset"]["featureCount"], 49)

    _create_zip_file = staticmethod(SoilMapImportServiceTest._create_zip_file)


class SoilMapUploadViewTest(TestCase):
    def test_only_superuser_can_open_soil_map_upload_form(self):
        """
        シナリオ:
        - 入力: 一般ユーザーとスーパーユーザーのログイン状態。
        - 処理: 土壌図ZIP取込画面へGETする。
        - 期待値: 一般ユーザーは403、スーパーユーザーはフォームを表示できること。
        """
        user_model = get_user_model()
        user = user_model.objects.create_user(username="operator", password="password")
        self.client.force_login(user)
        response = self.client.get(reverse("soil:soil_map_upload"))
        self.assertEqual(response.status_code, 403)

        administrator = user_model.objects.create_superuser(
            username="administrator", password="password", email="admin@example.com"
        )
        self.client.force_login(administrator)
        response = self.client.get(reverse("soil:soil_map_upload"))
        self.assertContains(response, "全国土壌図を取り込む")
