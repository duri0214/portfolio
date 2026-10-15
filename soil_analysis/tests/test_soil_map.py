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
    def test_import_archive_stores_all_polygons_and_activates_the_new_dataset(self):
        """
        シナリオ:
        - 入力: JGD_2000・必須属性を含む全国土壌図形式のZIP。
        - 処理: SoilMapImportServiceでZIPを取り込む。
        - 期待値: Polygonを保存し、新しいデータ版だけが有効になること。
        """
        with tempfile.TemporaryDirectory() as directory:
            archive_path = self._create_archive(Path(directory))

            dataset = SoilMapImportService.import_archive(archive_path)

        self.assertTrue(dataset.is_active)
        self.assertEqual(dataset.feature_count, 3)
        self.assertEqual(SoilMapPolygon.objects.filter(dataset=dataset).count(), 3)
        self.assertEqual(SoilMapPolygon.objects.first().prefecture_code, "02")

    def test_invalid_archive_keeps_the_current_dataset_active(self):
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
            archive_path = self._create_archive(Path(directory), crs="WGS_1984")

            with self.assertRaises(SoilMapImportError):
                SoilMapImportService.import_archive(archive_path)

        current.refresh_from_db()
        self.assertTrue(current.is_active)
        self.assertEqual(SoilMapDataset.objects.filter(is_active=True).count(), 1)

    @staticmethod
    def _create_archive(directory: Path, crs: str = "GCS_JGD_2000") -> Path:
        shape_path = directory / "national.shp"
        writer = shapefile.Writer(str(shape_path))
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
        writer.close()
        shape_path.with_suffix(".prj").write_text(crs, encoding="utf-8")
        archive_path = directory / "national.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            for suffix in (".shp", ".shx", ".dbf", ".prj"):
                archive.write(shape_path.with_suffix(suffix), f"national{suffix}")
        return archive_path


class SoilMapServiceTest(TestCase):
    def test_build_payload_returns_dominant_soil_for_each_prefecture(self):
        """
        シナリオ:
        - 入力: 青森県に黒ボク土2件、褐色森林土1件を持つ有効データ版。
        - 処理: SoilMapServiceで地図用payloadを作る。
        - 期待値: 青森県の代表土壌として黒ボク土と合計3件を返すこと。
        """
        with tempfile.TemporaryDirectory() as directory:
            SoilMapImportService.import_archive(
                SoilMapImportServiceTest._create_archive(Path(directory))
            )

        payload = SoilMapService.build_payload()
        aomori = next(area for area in payload["areas"] if area["code"] == 2)

        self.assertEqual(aomori["soilName"], "黒ボク土")
        self.assertEqual(aomori["polygonCount"], 3)
        self.assertEqual(payload["dataset"]["featureCount"], 3)

    _create_archive = staticmethod(SoilMapImportServiceTest._create_archive)


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
