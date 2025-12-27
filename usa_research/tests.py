from django.test import TestCase
from django.urls import reverse
from usa_research.domain.constants.almanac import MONTHLY_ANOMALIES


class IndexViewTests(TestCase):
    def test_index_view_status_code(self):
        """IndexViewが正常にレスポンスを返すことを確認"""
        response = self.client.get(reverse("usa:index"))
        self.assertEqual(response.status_code, 200)

    def test_index_view_context(self):
        """IndexViewのコンテキストに正しいデータが含まれていることを確認"""
        response = self.client.get(reverse("usa:index"))
        self.assertIn("monthly_anomalies", response.context)
        self.assertIn("theme_anomalies", response.context)
        self.assertIn("current_month", response.context)

        self.assertEqual(len(response.context["monthly_anomalies"]), 12)
        self.assertEqual(len(response.context["theme_anomalies"]), 3)
        self.assertTrue(1 <= response.context["current_month"] <= 12)

    def test_index_view_content(self):
        """IndexViewの表示内容に期待されるテキストが含まれていることを確認"""
        response = self.client.get(reverse("usa:index"))
        # 季節系のタイトルが少なくとも一つ含まれているか
        self.assertContains(response, MONTHLY_ANOMALIES[0]["title"])
        # カードのシャッフルボタンがあるか
        self.assertContains(response, "シャッフル")
