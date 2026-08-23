from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.tokens import account_activation_token
from lib.mail.mail_service import MailSendError


class RegistrationViewTest(TestCase):
    """ログイン画面から開始する新規登録とメール認証の画面遷移を検証する。"""

    def _registration_data(self, email: str = "new-user@example.com") -> dict[str, str]:
        """パスワード規約を満たす新規登録フォームの入力値を返す。"""
        return {
            "email": email,
            "password1": "Strong-password-123",
            "password2": "Strong-password-123",
        }

    def _activation_url(self, user) -> str:
        """テスト対象ユーザー用の認証URLを生成して返す。"""
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        return reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": token})

    def test_login_page_links_to_registration_page(self):
        """
        シナリオ:
        - 入力: 未ログインでログイン画面を開く。
        - 処理: 共通ログインテンプレートを描画する。
        - 期待値: 実装済みの新規登録画面へのリンクが表示されること。
        """
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("accounts:register"))
        self.assertNotContains(response, "未実装")

    @override_settings(MAIL_SEND_ENABLED=False, DEBUG=True)
    @patch("accounts.domain.service.registration.MailService")
    def test_registration_with_mail_disabled_does_not_connect_to_smtp(
        self, mail_service
    ):
        """
        シナリオ:
        - 入力: メール送信が無効な環境で有効なメールアドレスとパスワードを送信する。
        - 処理: 新規登録を実行する。
        - 期待値: 仮登録ユーザーが作成され、SMTPには接続せず開発確認用URLが表示されること。
        """
        response = self.client.post(
            reverse("accounts:register"), self._registration_data()
        )

        user = get_user_model().objects.get(email="new-user@example.com")
        self.assertFalse(user.is_active)
        self.assertContains(response, "本登録用メールを送信した扱いにしています")
        self.assertContains(response, "/accounts/activate/")
        mail_service.assert_not_called()

    @override_settings(MAIL_SEND_ENABLED=True)
    @patch("accounts.domain.service.registration.MailService")
    def test_registration_with_mail_enabled_sends_activation_mail(self, mail_service):
        """
        シナリオ:
        - 入力: メール送信が有効な環境で有効なメールアドレスとパスワードを送信する。
        - 処理: 新規登録を実行する。
        - 期待値: 仮登録ユーザーを作成し、既存MailServiceで本登録メールを1回送信すること。
        """
        response = self.client.post(
            reverse("accounts:register"), self._registration_data()
        )

        user = get_user_model().objects.get(email="new-user@example.com")
        self.assertFalse(user.is_active)
        self.assertContains(response, "本登録用のメールを送信しました")
        mail_service.return_value.send_mail.assert_called_once()

    @override_settings(MAIL_SEND_ENABLED=True)
    @patch("accounts.domain.service.registration.MailService")
    def test_registration_shows_error_and_removes_user_when_mail_sending_fails(
        self, mail_service
    ):
        """
        シナリオ:
        - 入力: メール送信が有効でMailServiceが送信失敗する状態の登録入力。
        - 処理: 新規登録を実行する。
        - 期待値: 送信失敗画面を表示し、再試行可能なよう仮登録ユーザーを残さないこと。
        """
        mail_service.return_value.send_mail.side_effect = MailSendError("failed")

        response = self.client.post(
            reverse("accounts:register"), self._registration_data()
        )

        self.assertContains(response, "メール送信に失敗しました")
        self.assertFalse(
            get_user_model().objects.filter(email="new-user@example.com").exists()
        )

    @override_settings(MAIL_SEND_ENABLED=False, DEBUG=False, IS_TESTING=False)
    def test_registration_hides_activation_url_when_mail_is_disabled_outside_development(
        self,
    ):
        """
        シナリオ:
        - 入力: メール送信が無効で開発・テストではない環境の登録入力。
        - 処理: 新規登録を実行する。
        - 期待値: SMTPへ接続せず、認証URLを画面へ表示しないこと。
        """
        response = self.client.post(
            reverse("accounts:register"), self._registration_data()
        )

        self.assertContains(response, "モックモード")
        self.assertNotContains(response, "/accounts/activate/")

    @override_settings(MAIL_SEND_ENABLED=False, DEBUG=True)
    def test_pending_user_cannot_log_in_until_activation(self):
        """
        シナリオ:
        - 入力: メール送信無効環境で仮登録されたユーザーの認証情報。
        - 処理: 本登録前にログインを試行し、認証URLを開く。
        - 期待値: 本登録前はログインできず、本登録後はログインできること。
        """
        self.client.post(reverse("accounts:register"), self._registration_data())
        user = get_user_model().objects.get(email="new-user@example.com")

        self.assertFalse(
            self.client.login(
                username="new-user@example.com", password="Strong-password-123"
            )
        )

        response = self.client.get(self._activation_url(user))
        user.refresh_from_db()

        self.assertContains(response, "本登録が完了しました")
        self.assertTrue(user.is_active)
        self.assertTrue(
            self.client.login(
                username="new-user@example.com", password="Strong-password-123"
            )
        )

    def test_activation_url_cannot_be_used_twice(self):
        """
        シナリオ:
        - 入力: 仮登録ユーザーに対して発行された同一の認証URL。
        - 処理: URLを2回開く。
        - 期待値: 初回だけ本登録され、2回目は無効リンクとして表示されること。
        """
        user = get_user_model().objects.create_user(
            username="new-user@example.com",
            email="new-user@example.com",
            password="Strong-password-123",
            is_active=False,
        )
        activation_url = self._activation_url(user)

        first_response = self.client.get(activation_url)
        second_response = self.client.get(activation_url)

        self.assertContains(first_response, "本登録が完了しました")
        self.assertContains(second_response, "無効な認証リンクです")

    @override_settings(ACCOUNT_ACTIVATION_TIMEOUT=60)
    def test_expired_activation_url_is_not_accepted(self):
        """
        シナリオ:
        - 入力: 有効期限を61秒に設定し、61秒前に発行した仮登録ユーザーの認証URL。
        - 処理: 認証URLを開く。
        - 期待値: ユーザーを本登録せず、期限切れ画面を表示すること。
        """
        user = get_user_model().objects.create_user(
            username="new-user@example.com",
            email="new-user@example.com",
            password="Strong-password-123",
            is_active=False,
        )
        issued_at = account_activation_token._now()
        with patch.object(account_activation_token, "_now", return_value=issued_at):
            activation_url = self._activation_url(user)
        with patch.object(
            account_activation_token,
            "_now",
            return_value=issued_at + timedelta(seconds=61),
        ):
            response = self.client.get(activation_url)

        user.refresh_from_db()
        self.assertContains(response, "認証リンクの有効期限が切れています")
        self.assertFalse(user.is_active)
