from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import Company, CompanyCategory


class AgriculturalCompanyUpdateViewTests(TestCase):
    def setUp(self):
        self.farmer_category = CompanyCategory.objects.create(name="農業法人")
        self.institution_category = CompanyCategory.objects.create(name="分析機関")
        self.company = Company.objects.create(
            name="更新前の農業法人",
            category=self.farmer_category,
            remark="更新前の備考",
        )
        self.institution = Company.objects.create(
            name="分析機関", category=self.institution_category
        )

    def test_agricultural_company_can_be_updated_from_detail_page(self):
        """
        シナリオ:
        - 入力: 名称と備考が登録済みの農業法人がある。
        - 処理: 詳細画面から編集画面を開き、名称と備考を変更して保存する。
        - 期待値: 詳細画面に戻り、変更後の内容と更新完了メッセージが表示される。
        """
        detail_url = reverse("soil:company_detail", kwargs={"pk": self.company.id})
        update_url = reverse("soil:company_update", kwargs={"pk": self.company.id})
        land_create_url = reverse(
            "soil:land_create", kwargs={"company_id": self.company.id}
        )

        detail_response = self.client.get(detail_url)
        self.assertContains(detail_response, update_url)
        self.assertContains(detail_response, "企業を編集")
        self.assertContains(detail_response, land_create_url, count=1)
        self.assertNotContains(detail_response, "編集（未実装）")
        self.assertLess(
            detail_response.content.decode().index(update_url),
            detail_response.content.decode().index("所属圃場"),
        )

        edit_response = self.client.get(update_url)
        self.assertContains(edit_response, "更新前の農業法人")
        self.assertContains(edit_response, "更新前の備考")

        update_response = self.client.post(
            update_url,
            {"name": "更新後の農業法人", "remark": "更新後の備考"},
            follow=True,
        )

        self.assertRedirects(update_response, detail_url)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "更新後の農業法人")
        self.assertEqual(self.company.remark, "更新後の備考")
        self.assertContains(update_response, "農業法人を更新しました。")
        self.assertContains(update_response, "更新後の農業法人")
        self.assertContains(update_response, "更新後の備考")

    def test_cancel_link_keeps_agricultural_company_unchanged(self):
        """
        シナリオ:
        - 入力: 編集前の農業法人がある。
        - 処理: 編集画面を開き、キャンセル導線を確認する。
        - 期待値: 詳細画面へ戻るリンクがあり、登録済みの内容は変更されない。
        """
        detail_url = reverse("soil:company_detail", kwargs={"pk": self.company.id})
        update_url = reverse("soil:company_update", kwargs={"pk": self.company.id})

        response = self.client.get(update_url)

        self.assertContains(response, f'href="{detail_url}"')
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, "更新前の農業法人")
        self.assertEqual(self.company.remark, "更新前の備考")

    def test_analysis_institution_cannot_use_agricultural_company_update_route(self):
        """
        シナリオ:
        - 入力: 分析機関が登録されている。
        - 処理: 農業法人用の編集 URL と詳細画面を開く。
        - 期待値: 編集 URL は 404 となり、詳細画面には農業法人用の編集導線が表示されない。
        """
        update_url = reverse("soil:company_update", kwargs={"pk": self.institution.id})

        update_response = self.client.get(update_url)
        detail_response = self.client.get(
            reverse("soil:company_detail", kwargs={"pk": self.institution.id})
        )

        self.assertEqual(update_response.status_code, 404)
        self.assertNotContains(detail_response, update_url)
