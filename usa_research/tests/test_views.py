from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from usa_research.models import Unit, FinancialResultWatch


class FinancialResultsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="test-user", email="test@example.com", password="password"
        )
        self.client.login(username="test-user", password="password")
        self.unit_cents, _ = Unit.objects.get_or_create(
            id=1, defaults={"name": "セント(¢)"}
        )
        self.unit_dollars, _ = Unit.objects.get_or_create(
            id=2, defaults={"name": "ドル(100M$)"}
        )

    def test_financial_results_list_view(self):
        FinancialResultWatch.objects.create(
            ticker="AMD",
            recorded_date="2023-01-01",
            quarter=1,
            eps_estimate=1.0,
            eps_actual=1.1,
            eps_unit=self.unit_cents,
            sales_estimate=100.0,
            sales_actual=110.0,
            sales_unit=self.unit_dollars,
            y_over_y_growth_rate=10.0,
            user=self.user,
        )
        response = self.client.get(reverse("usa:financial_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AMD")

    def test_financial_results_detail_view(self):
        FinancialResultWatch.objects.create(
            ticker="AMD",
            recorded_date="2023-01-01",
            quarter=1,
            eps_estimate=1.0,
            eps_actual=1.1,
            eps_unit=self.unit_cents,
            sales_estimate=100.0,
            sales_actual=110.0,
            sales_unit=self.unit_dollars,
            y_over_y_growth_rate=10.0,
            user=self.user,
        )
        response = self.client.get(
            reverse("usa:financial_results_detail", kwargs={"ticker": "AMD"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AMD")
        self.assertContains(response, "1Q")

    def test_financial_results_create_view_get(self):
        response = self.client.get(reverse("usa:financial_results_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "usa_research/financial_results/create.html")

    def test_financial_results_create_view_post(self):
        data = {
            "ticker": "SNOW",
            "recorded_date": "2023-01-01",
            "quarter": 1,
            "eps_estimate": 2.0,
            "eps_actual": 2.1,
            "eps_unit": self.unit_cents.id,
            "sales_estimate": 200.0,
            "sales_actual": 210.0,
            "sales_unit": self.unit_dollars.id,
            "y_over_y_growth_rate": 15.0,
            "eps_ok": True,
            "sales_ok": True,
            "guidance_ok": True,
        }
        response = self.client.post(reverse("usa:financial_results_create"), data)
        self.assertRedirects(response, reverse("usa:financial_results"))
        self.assertTrue(FinancialResultWatch.objects.filter(ticker="SNOW").exists())
