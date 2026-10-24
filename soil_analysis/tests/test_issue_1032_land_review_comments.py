from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.domain.service.land_review_comment_generation import (
    LandReviewCommentGenerationService,
)
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
    LandReview,
    LandReviewTemplate,
    SamplingMethod,
    SoilChemicalMeasurement,
    SoilHardnessMeasurement,
    Device,
)


class LandReviewCommentViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reviewer", password="password"
        )
        self.superuser = get_user_model().objects.create_superuser(
            username="administrator", password="password", email="admin@example.com"
        )
        category = CompanyCategory.objects.create(name="農業法人")
        self.company = Company.objects.create(name="テスト農園", category=category)
        area = JmaArea.objects.create(code="01", name="北海道")
        prefecture = JmaPrefecture.objects.create(
            code="0101", name="北海道", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="札幌", jma_prefecture=prefecture
        )
        city = JmaCity.objects.create(code="0101011", name="札幌市", jma_region=region)
        cultivation_type = CultivationType.objects.create(name="露地")
        self.land = Land.objects.create(
            name="第一圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=cultivation_type,
            owner=self.user,
            center="43.0,141.0",
        )
        crop = Crop.objects.create(name="キャベツ")
        method = SamplingMethod.objects.create(name="5点法", times=5)
        self.ledger = LandLedger.objects.create(
            land=self.land,
            land_period=LandPeriod.objects.create(name="春", year=2026),
            sampling_date=date(2026, 4, 1),
            analytical_agency=self.company,
            crop=crop,
            sampling_method=method,
            sampling_staff=self.user,
        )
        self.edit_url = reverse(
            "soil:land_review_edit",
            kwargs={"company_id": self.company.id, "land_ledger_id": self.ledger.id},
        )

    def test_manual_comment_is_created_updated_and_rendered_with_linebreaks(self):
        """
        シナリオ:
        - 入力: ログイン済み利用者と、改行を含む手入力の評価コメント。
        - 処理: 同じ台帳へ新規保存した後、別の本文で再保存して通知表を開く。
        - 期待値: 評価コメントは台帳ごとに1件だけ作成・更新され、改行を保って表示されること。
        """
        self.client.force_login(self.user)

        response = self.client.post(
            self.edit_url,
            {
                "source": "manual",
                "comment": "化学性を確認しました。\n物理性も継続して確認します。",
                "action": "save",
            },
        )
        self.assertRedirects(
            response,
            reverse(
                "soil:standard_report",
                kwargs={
                    "company_id": self.company.id,
                    "land_ledger_id": self.ledger.id,
                },
            ),
        )
        review = LandReview.objects.get(land_ledger=self.ledger)
        self.assertEqual(review.source, LandReview.Source.MANUAL)
        self.assertEqual(
            review.comment, "化学性を確認しました。\n物理性も継続して確認します。"
        )

        self.client.post(
            self.edit_url,
            {"source": "manual", "comment": "更新後の評価です。", "action": "save"},
        )
        self.assertEqual(LandReview.objects.filter(land_ledger=self.ledger).count(), 1)
        report = self.client.get(
            reverse(
                "soil:standard_report",
                kwargs={
                    "company_id": self.company.id,
                    "land_ledger_id": self.ledger.id,
                },
            )
        )
        self.assertContains(report, "更新後の評価です。")

    def test_template_crud_and_selection_copy_comment_to_ledger(self):
        """
        シナリオ:
        - 入力: ログイン済み利用者と、新規作成した定型評価コメント。
        - 処理: 定型コメントを作成し、台帳の評価コメントとして選択して保存する。
        - 期待値: 定型コメントは管理一覧にあり、その本文のコピーが台帳へ保存されること。
        """
        self.client.force_login(self.user)
        create_url = reverse("soil:land_review_template_create")
        response = self.client.post(
            create_url,
            {
                "name": "追肥の確認",
                "comment": "生育状況を確認し、必要に応じて追肥を検討してください。",
            },
        )
        self.assertRedirects(response, reverse("soil:land_review_template_list"))
        template = LandReviewTemplate.objects.get(name="追肥の確認")

        response = self.client.post(
            self.edit_url,
            {
                "source": "template",
                "template": template.id,
                "comment": "",
                "action": "save",
            },
        )
        self.assertEqual(response.status_code, 302)
        review = LandReview.objects.get(land_ledger=self.ledger)
        self.assertEqual(review.source, LandReview.Source.TEMPLATE)
        self.assertEqual(review.comment, template.comment)

        self.client.post(
            reverse("soil:land_review_template_update", kwargs={"pk": template.id}),
            {"name": "追肥の再確認", "comment": "更新後の定型文です。"},
        )
        template.refresh_from_db()
        self.assertEqual(template.comment, "更新後の定型文です。")
        self.client.post(
            reverse("soil:land_review_template_delete", kwargs={"pk": template.id})
        )
        self.assertFalse(LandReviewTemplate.objects.filter(pk=template.id).exists())
        self.assertEqual(
            LandReview.objects.get(land_ledger=self.ledger).comment, review.comment
        )

    def test_blank_comment_and_company_mismatch_are_rejected(self):
        """
        シナリオ:
        - 入力: 空白だけの手入力、および別企業のIDを含むURL。
        - 処理: 評価コメントの保存と編集画面の表示を要求する。
        - 期待値: 空白入力はエラーになり、企業と台帳の不一致は404になること。
        """
        self.client.force_login(self.user)
        response = self.client.post(
            self.edit_url,
            {"source": "manual", "comment": "   ", "action": "save"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "空白だけのコメントは保存できません。")
        self.assertFalse(LandReview.objects.filter(land_ledger=self.ledger).exists())

        other_company = Company.objects.create(
            name="別の農園", category=CompanyCategory.objects.get(name="農業法人")
        )
        mismatch_url = reverse(
            "soil:land_review_edit",
            kwargs={"company_id": other_company.id, "land_ledger_id": self.ledger.id},
        )
        self.assertEqual(self.client.get(mismatch_url).status_code, 404)

    def test_gpt_draft_is_limited_to_superuser_and_saved_only_after_confirmation(self):
        """
        シナリオ:
        - 入力: 一般利用者とスーパーユーザー、およびモックしたGPTの下書き。
        - 処理: それぞれが評価入力画面を開き、管理者だけが下書きを生成して保存する。
        - 期待値: GPT操作は管理者だけに表示・実行され、生成時は未保存で、保存後にGPT由来の評価として登録されること。
        """
        self.client.force_login(self.user)
        response = self.client.get(self.edit_url)
        self.assertNotContains(response, "GPTで下書きを作成する")
        forbidden = self.client.post(
            self.edit_url, {"source": "gpt", "action": "generate"}
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.superuser)
        with patch(
            "soil_analysis.views.LandReviewCommentGenerationService.generate",
            return_value="GPTが作成した下書きです。",
        ) as generate:
            response = self.client.post(
                self.edit_url, {"source": "gpt", "action": "generate"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GPTが作成した下書きです。")
        self.assertFalse(LandReview.objects.filter(land_ledger=self.ledger).exists())
        generate.assert_called_once_with(self.ledger)

        self.client.post(
            self.edit_url,
            {
                "source": "gpt",
                "comment": "確認して保存した下書きです。",
                "action": "save",
            },
        )
        review = LandReview.objects.get(land_ledger=self.ledger)
        self.assertEqual(review.source, LandReview.Source.GPT)
        self.assertEqual(review.comment, "確認して保存した下書きです。")

    def test_edit_requires_login(self):
        """
        シナリオ:
        - 入力: 未ログイン状態の利用者。
        - 処理: 台帳の評価コメント編集画面を開く。
        - 期待値: 保存画面へは進めず、ログイン画面へリダイレクトされること。
        """
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    @patch(
        "soil_analysis.domain.service.land_review_comment_generation.LandReviewCommentGenerator.generate",
        return_value="下書きです。",
    )
    def test_gpt_generation_receives_only_measurement_import_statuses(self, generate):
        """
        シナリオ:
        - 入力: 化学分析と土壌硬度の両方が取り込まれた台帳。
        - 処理: GPT下書き生成サービスを呼び出す。
        - 期待値: 数値を渡さず、両測定の取込済み状態を含むプロンプトで下書きを依頼すること。
        """
        SoilChemicalMeasurement.objects.create(land_ledger=self.ledger)
        device = Device.objects.create(name="硬度計")
        SoilHardnessMeasurement.objects.create(
            land_ledger=self.ledger,
            set_device=device,
            set_memory=1,
            set_datetime="2026-04-01T10:00:00+09:00",
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=10,
            pressure=1000,
            folder="第一圃場",
        )

        comment = LandReviewCommentGenerationService.generate(self.ledger)

        self.assertEqual(comment, "下書きです。")
        prompt = generate.call_args.args[0]
        self.assertIn("化学分析: 取り込み済み", prompt)
        self.assertIn("土壌硬度: 取り込み済み", prompt)
        self.assertNotIn("1000", prompt)
