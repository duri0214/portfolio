from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
    UserAttribute,
)


class LandEditingViewTests(TestCase):
    def setUp(self):
        self.category = CompanyCategory.objects.create(name="農業法人")
        self.company = Company.objects.create(name="テスト法人", category=self.category)
        self.user = get_user_model().objects.create_user(username="field-owner")
        UserAttribute.objects.create(user=self.user, role=UserAttribute.Role.OWNER)
        self.cultivation_type = CultivationType.objects.create(name="畑")
        self.updated_cultivation_type = CultivationType.objects.create(name="水田")
        area = JmaArea.objects.create(code="01", name="北海道")
        self.prefecture = JmaPrefecture.objects.create(
            code="0101", name="北海道", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="札幌", jma_prefecture=self.prefecture
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="札幌市", jma_region=region
        )
        self.land = Land.objects.create(
            name="編集前の圃場",
            company=self.company,
            jma_city=self.city,
            center="43.0,141.0",
            area=100,
            remark="編集前",
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )

    def edit_url(self):
        return reverse(
            "soil:land_update",
            kwargs={"company_id": self.company.id, "pk": self.land.id},
        )

    def detail_url(self):
        return reverse(
            "soil:land_detail",
            kwargs={"company_id": self.company.id, "pk": self.land.id},
        )

    def form_data(self, **overrides):
        data = {
            "name": "編集後の圃場",
            "jma_prefecture": self.city.jma_region.jma_prefecture_id,
            "jma_city": self.city.id,
            "center": "43.1,141.1",
            "area": "200",
            "remark": "編集後",
            "cultivation_type": self.updated_cultivation_type.id,
            "owner": self.user.id,
            "company-id": self.company.id,
        }
        data.update(overrides)
        return data

    def test_company_detail_has_edit_action_for_each_land(self):
        """
        シナリオ:
        - 入力: 農業法人詳細画面に圃場が表示されている。
        - 処理: 所属圃場の編集導線を確認する。
        - 期待値: 圃場編集画面へのリンクが表示されること。
        """
        response = self.client.get(
            reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )

        self.assertContains(response, self.edit_url())
        self.assertContains(response, "編集")

    def test_edit_form_prefills_existing_values(self):
        """
        シナリオ:
        - 入力: 既存の圃場を編集する画面を開く。
        - 処理: フォームの初期値を確認する。
        - 期待値: 既存の圃場情報と都道府県が初期表示されること。
        """
        response = self.client.get(self.edit_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"].initial["jma_prefecture"], self.prefecture.id
        )
        self.assertContains(response, 'value="編集前の圃場"')
        self.assertContains(response, "更新する")
        self.assertNotContains(response, 'name="company"')

    def test_land_can_be_updated_and_redirects_to_detail(self):
        """
        シナリオ:
        - 入力: 圃場編集フォームに変更後の圃場情報を入力する。
        - 処理: フォームを保存する。
        - 期待値: 圃場が更新され、圃場詳細画面へ戻ること。
        """
        response = self.client.post(self.edit_url(), self.form_data())

        self.assertRedirects(response, self.detail_url())
        self.land.refresh_from_db()
        self.assertEqual(self.land.name, "編集後の圃場")
        self.assertEqual(self.land.center, "43.1,141.1")
        self.assertEqual(self.land.area, 200)
        self.assertEqual(self.land.remark, "編集後")
        self.assertEqual(
            self.land.cultivation_type_id, self.updated_cultivation_type.id
        )
        self.assertEqual(self.land.company_id, self.company.id)

    def test_invalid_land_update_keeps_form_and_data(self):
        """
        シナリオ:
        - 入力: 圃場名に不正な値を入力する。
        - 処理: 圃場編集フォームを送信する。
        - 期待値: エラーと入力内容を表示し、保存前の圃場が残ること。
        """
        response = self.client.post(self.edit_url(), self.form_data(name="あの圃場"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "「あの」を含む圃場名は登録できなくなりました")
        self.assertContains(response, "あの圃場")
        self.land.refresh_from_db()
        self.assertEqual(self.land.name, "編集前の圃場")

    def test_edit_url_cannot_access_land_from_another_company(self):
        """
        シナリオ:
        - 入力: 別法人の ID を指定した圃場編集 URL がある。
        - 処理: 圃場編集 URL を開く。
        - 期待値: 編集画面を表示せず 404 を返すこと。
        """
        other_company = Company.objects.create(name="別法人", category=self.category)
        response = self.client.get(
            reverse(
                "soil:land_update",
                kwargs={"company_id": other_company.id, "pk": self.land.id},
            )
        )

        self.assertEqual(response.status_code, 404)
