from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
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
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
)


class HardnessViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="testuser")
        self.device = Device.objects.create(name="DIK-5531")

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
        )

    def test_hardness_association_field_group_view_get(self):
        # memory_anchor=1 でアクセス
        url = reverse(
            "soil:hardness_association_field_group", kwargs={"memory_anchor": 1}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "soil_analysis/hardness/association/field_group.html"
        )
        # AttributeError: 'list' object has no attribute 'values_list' が発生しなければ成功
        self.assertEqual(response.context["memory_anchor"], 1)
        self.assertEqual(response.context["min_memory"], 1)
        self.assertEqual(response.context["max_memory"], 1)
        self.assertEqual(response.context["folder_name"], "Folder1")

    def test_hardness_success_view_uses_current_import_folders(self):
        """
        シナリオ:
        - 入力: DBには過去取り込みのFolder1と今回取り込みのFIELD001_ROUND02が混在し、セッションにはFIELD001_ROUND02だけを保持する。
        - 処理: 硬度アップロード成功画面を表示する。
        - 期待値: 取り込みデータ集計と総レコード数はFIELD001_ROUND02だけを対象にし、表示補足付き圃場を未作成扱いしない。
        """
        Land.objects.create(
            name="FIELD001（点検用圃場）",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )
        SoilHardnessMeasurement.objects.create(
            set_device=self.device,
            set_memory=2,
            set_datetime=datetime(2023, 7, 2, 10, 0, 0),
            set_depth=50,
            set_spring=1,
            set_cone=1,
            depth=1,
            pressure=110,
            folder="FIELD001_ROUND02",
        )
        SoilHardnessMeasurement.objects.create(
            set_device=self.device,
            set_memory=3,
            set_datetime=datetime(2023, 7, 2, 10, 0, 0),
            set_depth=50,
            set_spring=1,
            set_cone=1,
            depth=1,
            pressure=120,
            folder="FIELD001_ROUND02",
        )
        session = self.client.session
        session["hardness_import_folders"] = ["FIELD001_ROUND02"]
        session.save()

        response = self.client.get(reverse("soil:hardness_success"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_records"], 2)
        self.assertEqual(
            [stats.folder for stats in response.context["folder_stats"]],
            ["FIELD001_ROUND02"],
        )
        self.assertEqual(response.context["missing_lands"], [])
