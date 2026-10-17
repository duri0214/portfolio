import tempfile
import zipfile
from pathlib import Path

import shapefile
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from soil_analysis.domain.service.soil_classification import SoilClassificationService
from soil_analysis.domain.service.soil_map_import import (
    SoilMapImportError,
    SoilMapImportService,
)
from soil_analysis.models import SoilMapDataset, SoilMapPolygon


class SoilMapImportServiceTest(TestCase):
    def test_import_soil_map_from_zip_stores_all_polygons_and_activates_the_new_dataset(
        self,
    ):
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

            dataset = SoilMapImportService.import_soil_map_from_zip(zip_path)

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
                SoilMapImportService.import_soil_map_from_zip(zip_path)

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
                SoilMapImportService.import_soil_map_from_zip(zip_path)

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
                SoilMapImportService.import_soil_map_from_zip(zip_path)

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


class SoilClassificationServiceTest(TestCase):
    def test_soil_name_removes_empty_parentheses(self):
        """
        シナリオ:
        - 入力: 空の括弧を含む土壌名。
        - 処理: 画面表示用の土壌名を正規化する。
        - 期待値: 空の括弧を除いた名称になること。
        """
        self.assertEqual(
            SoilClassificationService.normalize_soil_name("細粒質（）灰色低地土"),
            "細粒質灰色低地土",
        )

    def test_soil_group_code_is_converted_to_a_readable_name(self):
        """
        シナリオ:
        - 入力: 土壌群コード D6。
        - 処理: 画面表示用の土壌群名と解説URLを取得する。
        - 期待値: アロフェン質黒ボク土と対応する解説URLを返すこと。
        """
        self.assertEqual(
            SoilClassificationService.get_soil_group_name("D6"), "アロフェン質黒ボク土"
        )
        self.assertEqual(
            SoilClassificationService.get_soil_group_url("D6"),
            "https://soil-inventory.rad.naro.go.jp/explain/D6.html",
        )
        self.assertIn("火山灰", SoilClassificationService.get_soil_group_summary("D6"))


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
        self.assertContains(response, "地図データを管理")
        self.assertContains(response, reverse("soil:municipality_boundary_upload"))
        self.assertContains(response, reverse("soil:municipality_soil_recalculate"))
        self.assertContains(response, "全国_20.zip")
        self.assertContains(response, "N03-YYYY0101_GML.zip")
        self.assertNotContains(response, "直接ダウンロード")


class SoilPointSearchViewTest(TestCase):
    def setUp(self):
        self.dataset = SoilMapDataset.objects.create(
            source_file_name="全国_20.zip",
            source_sha256="1" * 64,
            source_crs="GCS_JGD_2000",
            feature_count=3,
            is_active=True,
            imported_at=timezone.now(),
        )
        SoilMapPolygon.objects.create(
            dataset=self.dataset,
            prefecture_code="11",
            soil_group_code="D6",
            soil_subgroup_code="D6h",
            soil_series_code="D6h2",
            soil_name="淡色アロフェン質黒ボク土",
            coordinates=[_square(139.4, 35.8, 139.5, 35.9)],
            min_lng=139.4,
            min_lat=35.8,
            max_lng=139.5,
            max_lat=35.9,
        )

    def test_search_displays_saved_soil_classification_and_shared_url(self):
        """
        シナリオ:
        - 入力: 淡色アロフェン質黒ボク土のPolygon内にある35.861231, 139.432468。
        - 処理: 地点検索画面を緯度・経度付きでGETする。
        - 期待値: 土壌名、分類記号、公式解説、地点指定地図、同じ座標を含む共有URLを表示すること。
        """
        response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "35.861231", "longitude": "139.432468"},
        )

        self.assertContains(response, "この地域の土壌から読み取れること")
        self.assertContains(response, "淡色アロフェン質黒ボク土")
        self.assertContains(response, "D6h2")
        self.assertContains(
            response, "https://soil-inventory.rad.naro.go.jp/explain/D6.html"
        )
        self.assertContains(
            response,
            "lat=35.861231&amp;lng=139.432468&amp;zoom=12",
        )
        self.assertContains(response, "地域全体を詳しく見る")

    def test_search_reports_missing_polygon_within_dataset_extent(self):
        """
        シナリオ:
        - 入力: 外周Polygonの穴にあたる地点と、同じ外接矩形を持つ土壌図。
        - 処理: 地点検索画面をGETする。
        - 期待値: 成功結果にせず、該当Polygonがない理由と一次情報への導線を表示すること。
        """
        SoilMapPolygon.objects.filter(dataset=self.dataset).delete()
        outer_ring = _square(139.4, 35.8, 139.5, 35.9)
        inner_ring = list(reversed(_square(139.43, 35.85, 139.44, 35.86)))
        SoilMapPolygon.objects.create(
            dataset=self.dataset,
            prefecture_code="11",
            soil_group_code="D6",
            soil_subgroup_code="D6h",
            soil_series_code="D6h2",
            soil_name="淡色アロフェン質黒ボク土",
            coordinates=[outer_ring, inner_ring],
            min_lng=139.4,
            min_lat=35.8,
            max_lng=139.5,
            max_lat=35.9,
        )

        response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "35.855", "longitude": "139.435"},
        )

        self.assertContains(response, "指定地点に一致する土壌図Polygonがありません")
        self.assertNotContains(response, "この地域の土壌から読み取れること")

    def test_search_reports_non_soil_classification(self):
        """
        シナリオ:
        - 入力: 市街地／水域などを表すZ3のPolygon内にある地点。
        - 処理: 地点検索画面をGETする。
        - 期待値: 土壌分類の成功結果にせず、市街地／水域などである理由を表示すること。
        """
        SoilMapPolygon.objects.create(
            dataset=self.dataset,
            prefecture_code="11",
            soil_group_code="Z3",
            soil_subgroup_code="Z3",
            soil_series_code="Z3",
            soil_name="市街地／水域など",
            coordinates=[_square(139.6, 35.8, 139.7, 35.9)],
            min_lng=139.6,
            min_lat=35.8,
            max_lng=139.7,
            max_lat=35.9,
        )

        response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "35.85", "longitude": "139.65"},
        )

        self.assertContains(response, "この地点は「市街地／水域など」です")
        self.assertNotContains(response, "この地域の土壌から読み取れること")

    def test_search_reports_invalid_coordinates_and_unavailable_data(self):
        """
        シナリオ:
        - 入力: 範囲外の緯度、または有効な土壌図を削除した状態の正しい座標。
        - 処理: 地点検索画面をGETする。
        - 期待値: 入力エラーとデータ未登録を、それぞれ利用者が区別できること。
        """
        invalid_response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "91", "longitude": "139.432468"},
        )
        self.assertContains(invalid_response, "90 以下")

        outside_response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "34.0", "longitude": "139.432468"},
        )
        self.assertContains(outside_response, "保存済み土壌図の対象範囲外です")

        SoilMapDataset.objects.all().delete()
        unavailable_response = self.client.get(
            reverse("soil:soil_map_point_search"),
            {"latitude": "35.861231", "longitude": "139.432468"},
        )
        self.assertContains(unavailable_response, "土壌図データが未登録です")


def _square(min_lng, min_lat, max_lng, max_lat):
    return [
        [min_lng, min_lat],
        [min_lng, max_lat],
        [max_lng, max_lat],
        [max_lng, min_lat],
        [min_lng, min_lat],
    ]
