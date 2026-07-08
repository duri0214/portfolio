from django.test import TestCase
from django.urls import reverse


class TaxonomyIndexViewTest(TestCase):
    def test_index_page_wraps_classification_chart_in_scroll_area(self):
        """
        シナリオ:
        - 入力: taxonomyの分類データが空でも表示できるDB状態。
        - 処理: 分類グラフを含むtaxonomyトップページを表示する。
        - 期待値: 分類グラフが途中で切れないよう、スクロール可能な領域で囲まれていること。
        """
        response = self.client.get(reverse("txo:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "taxonomy-chart-scroll")
        self.assertContains(response, "overflow: auto")
