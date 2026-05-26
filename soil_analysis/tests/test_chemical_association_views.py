from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    Crop,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
)


class ChemicalAssociationViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")

        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="Test Company", category=category)
        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        city = JmaCity.objects.create(code="0101011", name="テスト市", jma_region=region)

        cultivation_type = CultivationType.objects.create(name="露地")
        crop = Crop.objects.create(name="キャベツ")
        sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        period = LandPeriod.objects.create(name="2024年春", year=2024)

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

    def test_upload_form_does_not_show_target_ledger_field(self):
        response = self.client.get(reverse("soil:chemical_upload"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "川田研究所 XLSX")
        self.assertNotContains(response, 'id="id_land_ledger_id"')

    def test_row_confirmation_flow_works_without_base_ledger(self):
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
                        "cec": None,
                        "cao": None,
                        "mgo": None,
                        "k2o": None,
                        "lime_saturation": None,
                        "magnesia_saturation": None,
                        "potash_saturation": None,
                        "base_saturation": None,
                        "p2o5": None,
                        "phosphorus_absorption": None,
                        "nh4n": None,
                        "no3n": None,
                        "humus": None,
                        "bulk_density": None,
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "overwrite": False,
            "total_rows": 1,
        }
        session.save()

        row_url = reverse(
            "soil:chemical_association_field_row", kwargs={"row_index": 0}
        )
        response = self.client.get(row_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "圃場A")

        response = self.client.post(row_url, {"land_ledger": self.ledger.id})
        self.assertRedirects(response, reverse("soil:chemical_association"))

        updated_session = self.client.session["chemical_import_session"]["rows"][0]
        self.assertEqual(updated_session["status"], "confirmed")
        self.assertEqual(updated_session["selected_ledger_id"], self.ledger.id)
