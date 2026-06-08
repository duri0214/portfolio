from datetime import datetime
from unittest.mock import patch

from django import forms
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse

from soil_analysis.models import (
    SoilHardnessMeasurement,
    Device,
    Land,
    LandLedger,
    Company,
    CompanyCategory,
    Crop,
    LandPeriod,
    CultivationType,
    SamplingMethod,
    LandBlock,
    JmaCity,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
)
from soil_analysis.views import HardnessUploadView


class HardnessPlotAutoGenerationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="testuser")
        category = CompanyCategory.objects.create(name="Test Category")
        self.company = Company.objects.create(name="Test Company", category=category)

        area = JmaArea.objects.create(code="01", name="Test Area")
        pref = JmaPrefecture.objects.create(
            code="0101", name="Test Pref", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="Test Region", jma_prefecture=pref
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="Test City", jma_region=region
        )

        self.cultivation_type = CultivationType.objects.create(name="Open Field")
        self.crop = Crop.objects.create(name="Test Crop")
        self.period = LandPeriod.objects.create(year=2023, name="2023")
        self.sampling_method = SamplingMethod.objects.create(name="5-point", times=5)
        self.device = Device.objects.create(name="DIK-5531")

        self.land = Land.objects.create(
            name="Field A",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )
        self.ledger = LandLedger.objects.create(
            land=self.land,
            crop=self.crop,
            land_period=self.period,
            sampling_date=datetime(2023, 7, 1).date(),
            analytical_agency=self.company,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        self.land_block = LandBlock.objects.create(name="A1")

    @patch("soil_analysis.views.HardnessPlotGenerationService.generate_and_save_plots")
    def test_auto_generation_on_success_view(self, mock_generate):
        """成功画面表示時に自動で画像生成が呼ばれることを確認"""
        # 測定データの作成
        SoilHardnessMeasurement.objects.create(
            set_device=self.device,
            set_memory=1,
            set_datetime=datetime(2023, 7, 1, 10, 0, 0),
            set_depth=50,
            set_spring=1,
            set_cone=1,
            depth=1,
            pressure=100,
            folder="Folder1",
            land_ledger=self.ledger,
            land_block=self.land_block,
        )

        session = self.client.session
        session["hardness_import_folders"] = ["Folder1"]
        session.save()

        # 初回アクセス
        response = self.client.get(reverse("soil:hardness_association_success"))
        self.assertEqual(response.status_code, 200)

        # モックが呼ばれたことを確認 (IDリストが引数に渡されていること)
        mock_generate.assert_called_once_with([self.ledger.id])

        # セッションフラグが立っていることを確認
        self.assertTrue(self.client.session.get("hardness_plots_generated"))

        # 2回目アクセスでは呼ばれないことを確認
        mock_generate.reset_mock()
        response = self.client.get(reverse("soil:hardness_association_success"))
        mock_generate.assert_not_called()

    def test_flag_reset_on_upload(self):
        """アップロード時にフラグがリセットされることを確認"""
        from django.core.files.uploadedfile import SimpleUploadedFile

        factory = RequestFactory()
        dummy_file = SimpleUploadedFile("test.zip", b"dummy content")
        request = factory.post(reverse("soil:hardness_upload"), {"file": dummy_file})

        # セッションのモック
        from django.contrib.sessions.middleware import SessionMiddleware

        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session["hardness_plots_generated"] = True
        request.session.save()

        # Viewのインスタンスを作って実行
        view = HardnessUploadView()
        view.request = request
        view.request.resolver_match = type("obj", (object,), {"app_name": "soil"})

        # form_valid 内の処理をモック
        with patch(
            "soil_analysis.views.ZipFileService.handle_uploaded_zip",
            return_value="/tmp/dummy",
        ):
            with patch("os.path.exists", return_value=False):
                view.form_valid(forms.Form())

        self.assertFalse(request.session["hardness_plots_generated"])

    def test_generate_and_save_plots_to_land_ledger(self):
        """実際に画像を生成してLandLedgerに保存されることを確認"""
        from soil_analysis.domain.service.hardness_plot_generation import (
            HardnessPlotGenerationService,
        )

        # 測定データの作成 (1点だと表面プロットが作れない可能性があるので、最低2地点以上のグリッドを作る)
        block_a2 = LandBlock.objects.create(name="A2")
        memory = 1
        for block in [self.land_block, block_a2]:
            for depth in [1, 5]:
                SoilHardnessMeasurement.objects.create(
                    set_device=self.device,
                    set_memory=memory,
                    set_datetime=datetime(2023, 7, 1, 10, 0, 0),
                    set_depth=50,
                    set_spring=1,
                    set_cone=1,
                    depth=depth,
                    pressure=100 + depth,
                    folder="Folder1",
                    land_ledger=self.ledger,
                    land_block=block,
                )
                memory += 1

        # 実行前の画像が空であることを確認
        self.assertFalse(bool(self.ledger.hardness_image))

        # 実行
        success_count, errors = HardnessPlotGenerationService.generate_and_save_plots(
            [self.ledger.id]
        )

        # 検証
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(success_count, 1)

        self.ledger.refresh_from_db()
        self.assertTrue(bool(self.ledger.hardness_image))
        self.assertTrue(self.ledger.hardness_image.name.startswith("hardness_images/"))
