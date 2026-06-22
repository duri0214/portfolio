from django.urls import reverse

from django.test import TestCase

from .forms import UploadFileForm
from .models import Bank


class MufgDepositUploadViewTests(TestCase):
    def test_create_bank_account_from_upload_page(self):
        """
        シナリオ:
        - 入力: MUFGの金融機関コード、店番、口座番号を含む口座登録フォーム。
        - 処理: MUFG普通預金CSVアップロード画面へ口座登録POSTを送信する。
        - 期待値: Bankが作成され、アップロード画面へリダイレクトされること。
        """
        url = reverse("bank:mufg_deposit_upload")

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
        - 処理: MUFG普通預金CSVアップロード画面へ口座登録POSTを送信する。
        - 期待値: Bankは作成されず、登録フォームのエラーが画面に返ること。
        """
        response = self.client.post(
            reverse("bank:mufg_deposit_upload"),
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
