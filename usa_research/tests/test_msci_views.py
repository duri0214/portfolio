import datetime

from django.test import TestCase, Client
from django.urls import reverse

from usa_research.models import MsciCountryWeightReport


class MsciReportViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # テストデータの作成
        self.report1 = MsciCountryWeightReport.objects.create(
            report_date=datetime.date(2024, 4, 1),
            summary_md="Summary 2024-04-01",
            pdf_url="http://example.com/20240401.pdf",
        )
        self.report2 = MsciCountryWeightReport.objects.create(
            report_date=datetime.date(2024, 5, 1),
            summary_md="Summary 2024-05-01",
            pdf_url="http://example.com/20240501.pdf",
        )

    def test_index_view_shows_latest_report_by_default(self):
        response = self.client.get(reverse("usa:index"))
        self.assertEqual(response.status_code, 200)
        # 最新のレポート（5/1）が表示されていることを確認
        self.assertEqual(response.context["msci_report"], self.report2)
        self.assertContains(response, "2024/05/01")
        self.assertContains(response, "Summary 2024-05-01")

    def test_index_view_shows_selected_report(self):
        # クエリパラメータで過去の日付を指定
        response = self.client.get(reverse("usa:index") + "?report_date=2024-04-01")
        self.assertEqual(response.status_code, 200)
        # 指定したレポート（4/1）が表示されていることを確認
        self.assertEqual(response.context["msci_report"], self.report1)
        self.assertContains(response, "2024/04/01")
        self.assertContains(response, "Summary 2024-04-01")

    def test_index_view_context_contains_all_report_dates(self):
        response = self.client.get(reverse("usa:index"))
        self.assertIn("msci_report_dates", response.context)
        dates = response.context["msci_report_dates"]
        self.assertEqual(len(dates), 2)
        self.assertEqual(dates[0], self.report2.report_date)
        self.assertEqual(dates[1], self.report1.report_date)

    def test_is_latest_report_flag(self):
        # デフォルト（最新）
        response = self.client.get(reverse("usa:index"))
        self.assertTrue(response.context["is_latest_report"])
        self.assertNotContains(response, 'disabled aria-disabled="true" tabindex="-1"')

        # 過去分
        response = self.client.get(reverse("usa:index") + "?report_date=2024-04-01")
        self.assertFalse(response.context["is_latest_report"])
        self.assertContains(response, "disabled")
        self.assertContains(response, 'aria-disabled="true"')

    def test_dropdown_contains_dates(self):
        response = self.client.get(reverse("usa:index"))
        self.assertContains(response, '<select id="report-date-select"')
        self.assertContains(response, "2024/05/01")
        self.assertContains(response, "2024/04/01")
