from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
    Crop,
    CultivationType,
    LandBlock,
)


class ChemicalAssociationReproTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")
        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="Test Company", category=category)
        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        city = JmaCity.objects.create(
            code="0101011", name="テスト市", jma_region=region
        )
        cultivation_type = CultivationType.objects.create(name="露地")
        crop = Crop.objects.create(name="キャベツ")
        sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        period = LandPeriod.objects.create(name="2024年春", year=2024)
        # LandBlockを作成 (1, 3, 5, 7, 9 が必要)
        for i in range(1, 10):
            LandBlock.objects.create(id=i, name=f"Block {i}")

        land = Land.objects.create(
            name="圃場A",
            company=self.company,
            jma_city=city,
            cultivation_type=cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )
        self.ledger = LandLedger.objects.create(
            land=land,
            land_period=period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=crop,
            sampling_method=sampling_method,
            sampling_staff=self.user,
        )

    def test_save_all_redirects_to_success(self):
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": 10.0,
                        "cao": 100.0,
                        "mgo": 50.0,
                        "k2o": 30.0,
                        "lime_saturation": 80.0,
                        "magnesia_saturation": 15.0,
                        "potash_saturation": 5.0,
                        "base_saturation": 100.0,
                        "p2o5": 20.0,
                        "phosphorus_absorption": 1000.0,
                        "nh4n": 1.0,
                        "no3n": 2.0,
                        "humus": 3.0,
                        "bulk_density": 1.0,
                    },
                    "selected_ledger_id": self.ledger.id,
                    "status": "confirmed",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        url = reverse("soil:chemical_association")
        # btn_save_all を含めて POST
        response = self.client.post(url, {"btn_save_all": "1"})

        # 成功画面へのリダイレクトを期待
        if response.status_code != 302 or response.url != reverse(
            "soil:chemical_association_success"
        ):
            print(f"DEBUG: Redirected to {response.url}")
            from django.contrib.messages import get_messages

            messages = [m.message for m in get_messages(response.wsgi_request)]
            print(f"DEBUG: Messages: {messages}")

        self.assertRedirects(response, reverse("soil:chemical_association_success"))

        # セッションがクリアされていることを確認
        self.assertNotIn("chemical_import_session", self.client.session)
        self.assertIn("chemical_import_result", self.client.session)
