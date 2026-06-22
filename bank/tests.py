from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from datetime import date

from django.test import TestCase

from .forms import UploadFileForm
from .models import (
    Bank,
    DepositSummaryCategory,
    DepositSummaryMaster,
    MufgDepositCsvRaw,
)


class MufgDepositUploadViewTests(TestCase):
    def test_create_bank_account_from_manage_page(self):
        """
        シナリオ:
        - 入力: MUFGの金融機関コード、店番、口座番号を含む口座登録フォーム。
        - 処理: 口座登録画面へ口座登録POSTを送信する。
        - 期待値: Bankが作成され、口座登録画面へリダイレクトされること。
        """
        url = reverse("bank:bank_account_manage")

        response = self.client.post(
            url,
            {
                "form_type": "bank_account",
                "name": "三菱UFJ銀行（生活費）",
                "financial_code": "0005",
                "branch_code": "123",
                "account_number": "1234567",
                "remark": "MUFG Eco通帳CSV対応",
            },
        )

        self.assertRedirects(response, url)
        self.assertTrue(
            Bank.objects.filter(
                financial_code="0005",
                branch_code="123",
                account_number="1234567",
            ).exists()
        )

    def test_create_bank_account_rejects_invalid_branch_code(self):
        """
        シナリオ:
        - 入力: 店番が3桁数字ではない口座登録フォーム。
        - 処理: 口座登録画面へ口座登録POSTを送信する。
        - 期待値: Bankは作成されず、登録フォームのエラーが画面に返ること。
        """
        response = self.client.post(
            reverse("bank:bank_account_manage"),
            {
                "form_type": "bank_account",
                "name": "三菱UFJ銀行（生活費）",
                "financial_code": "0005",
                "branch_code": "12",
                "account_number": "1234567",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Bank.objects.count(), 0)
        self.assertFormError(
            response.context["bank_form"],
            "branch_code",
            "店番は3桁の数字で入力してください。",
        )

    def test_upload_form_lists_created_bank_accounts(self):
        """
        シナリオ:
        - 入力: 登録済みのBankが1件ある状態。
        - 処理: UploadFileFormを初期化する。
        - 期待値: 対象口座の選択肢に登録済みBankが含まれること。
        """
        bank = Bank.objects.create(
            name="三菱UFJ銀行（生活費）",
            financial_code="0005",
            branch_code="123",
            account_number="1234567",
        )

        form = UploadFileForm()

        self.assertQuerySetEqual(form.fields["bank"].queryset, [bank])

    def test_create_bank_accounts_from_csv(self):
        """
        シナリオ:
        - 入力: 2件の口座情報を含むCSVファイル。
        - 処理: 口座登録画面へ口座CSV登録POSTを送信する。
        - 期待値: CSV内の口座がBankとして登録されること。
        """
        csv_content = (
            "name,financial_code,branch_code,account_number,remark\n"
            "三菱UFJ銀行（生活費）,0005,123,1234567,MUFG Eco通帳CSV対応\n"
            "三菱UFJ銀行（仕事用）,0005,456,7654321,\n"
        )
        uploaded_file = SimpleUploadedFile(
            "banks.csv",
            csv_content.encode("utf-8-sig"),
            content_type="text/csv",
        )
        url = reverse("bank:bank_account_manage")

        response = self.client.post(
            url,
            {"form_type": "bank_account_csv", "file": uploaded_file},
        )

        self.assertRedirects(response, url)
        self.assertEqual(Bank.objects.count(), 2)
        self.assertTrue(
            Bank.objects.filter(
                financial_code="0005",
                branch_code="456",
                account_number="7654321",
            ).exists()
        )

    def test_create_bank_accounts_from_csv_rolls_back_invalid_row(self):
        """
        シナリオ:
        - 入力: 1行目は正常、2行目は店番が不正なCSVファイル。
        - 処理: 口座登録画面へ口座CSV登録POSTを送信する。
        - 期待値: 途中まで登録されず、Bankが1件も作成されないこと。
        """
        csv_content = (
            "name,financial_code,branch_code,account_number,remark\n"
            "三菱UFJ銀行（生活費）,0005,123,1234567,MUFG Eco通帳CSV対応\n"
            "三菱UFJ銀行（不正）,0005,12,7654321,\n"
        )
        uploaded_file = SimpleUploadedFile(
            "banks.csv",
            csv_content.encode("utf-8-sig"),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("bank:bank_account_manage"),
            {"form_type": "bank_account_csv", "file": uploaded_file},
        )

        self.assertRedirects(response, reverse("bank:bank_account_manage"))
        self.assertEqual(Bank.objects.count(), 0)

    def test_upload_page_keeps_only_deposit_csv_upload_form(self):
        """
        シナリオ:
        - 入力: 口座登録機能を別ページに分離した状態。
        - 処理: MUFG普通預金CSVアップロード画面を表示する。
        - 期待値: アップロード画面には口座登録フォームが表示されないこと。
        """
        response = self.client.get(reverse("bank:mufg_deposit_upload"))

        self.assertContains(response, "ファイル アップロード")
        self.assertNotContains(response, "手入力で登録")
        self.assertNotContains(response, "CSVで登録")

    def test_anyone_can_download_bank_account_sample_csv(self):
        """
        シナリオ:
        - 入力: ログインしていない状態。
        - 処理: 口座CSVサンプルのダウンロードURLへGETする。
        - 期待値: CSVファイルとしてサンプル口座2件が返ること。
        """
        response = self.client.get(reverse("bank:bank_account_sample_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(
            'attachment; filename="bank_accounts_sample.csv"',
            response["Content-Disposition"],
        )
        content = response.content.decode("utf-8")
        self.assertIn("name,financial_code,branch_code,account_number,remark", content)
        self.assertIn("三菱UFJ銀行（プライベート）,0005,000,0000000", content)
        self.assertIn("三菱UFJ銀行（仕事用）,0005,111,1111111", content)

    def test_manage_page_shows_sample_csv_download_link(self):
        """
        シナリオ:
        - 入力: 口座登録画面を表示できる状態。
        - 処理: 口座登録画面を表示する。
        - 期待値: サンプルCSVのダウンロードリンクが表示されること。
        """
        response = self.client.get(reverse("bank:bank_account_manage"))

        self.assertContains(response, "サンプルCSV")
        self.assertContains(response, reverse("bank:bank_account_sample_csv"))
        self.assertNotContains(response, "disabled")

    def test_category_monthly_defaults_to_payment_and_includes_detail_data(self):
        """
        シナリオ:
        - 入力: 同じカテゴリに出金と入金の明細がある状態。
        - 処理: カテゴリ別月次集計をデフォルト条件で表示する。
        - 期待値: 出金合計が表示対象となり、クリック詳細用データにも出金明細だけが含まれること。
        """
        bank = self.create_category_monthly_transactions()

        response = self.client.get(
            reverse("bank:mufg_analysis_category_monthly"), {"bank": bank.id}
        )

        self.assertEqual(response.context["amount_type"], "payment")
        self.assertEqual(response.context["amount_label"], "出金")
        self.assertEqual(response.context["pivot_table"][0]["total"], 1200)
        self.assertEqual(
            response.context["pivot_table"][0]["category_values"][0]["amount"], 1200
        )
        details = response.context["detail_data"]["2026-01|カード"]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["payment_amount"], 1200)
        self.assertContains(response, "月別摘要別詳細")
        self.assertContains(response, 'value="payment"')
        self.assertContains(response, 'value="deposit"')

    def test_category_monthly_can_switch_to_deposit(self):
        """
        シナリオ:
        - 入力: 同じカテゴリに出金と入金の明細がある状態。
        - 処理: amount_type=deposit でカテゴリ別月次集計を表示する。
        - 期待値: 入金合計が表示対象となり、クリック詳細用データにも入金明細だけが含まれること。
        """
        bank = self.create_category_monthly_transactions()

        response = self.client.get(
            reverse("bank:mufg_analysis_category_monthly"),
            {"bank": bank.id, "amount_type": "deposit"},
        )

        self.assertEqual(response.context["amount_type"], "deposit")
        self.assertEqual(response.context["amount_label"], "入金")
        self.assertEqual(response.context["pivot_table"][0]["total"], 5000)
        self.assertEqual(
            response.context["pivot_table"][0]["category_values"][0]["amount"], 5000
        )
        details = response.context["detail_data"]["2026-01|カード"]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["deposit_amount"], 5000)

    @staticmethod
    def create_category_monthly_transactions():
        bank = Bank.objects.create(
            name="三菱UFJ銀行（生活費）",
            financial_code="0005",
            branch_code="123",
            account_number="1234567",
        )
        category = DepositSummaryCategory.objects.create(name="カード")
        DepositSummaryMaster.objects.create(summary="カード利用", category=category)
        MufgDepositCsvRaw.objects.create(
            bank=bank,
            trade_date=date(2026, 1, 10),
            summary="カード利用",
            summary_detail="スーパー",
            payment_amount=1200,
            deposit_amount=None,
            balance=9800,
            inout_type="出金",
        )
        MufgDepositCsvRaw.objects.create(
            bank=bank,
            trade_date=date(2026, 1, 15),
            summary="カード利用",
            summary_detail="返金",
            payment_amount=None,
            deposit_amount=5000,
            balance=14800,
            inout_type="入金",
        )
        return bank
