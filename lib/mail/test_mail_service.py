import unittest
from unittest.mock import patch, MagicMock

from lib.mail.mail_service import MailService, MailSendError


class TestMailService(unittest.TestCase):

    def setUp(self):
        # 環境変数をモックする
        self.env_patcher = patch.dict(
            "os.environ",
            {
                "MAIL_SMTP_HOST": "smtp.test.com",
                "MAIL_SMTP_PORT": "587",
                "MAIL_SMTP_USER": "test@example.com",
                "MAIL_SMTP_PASSWORD": "password",
                "MAIL_USE_TLS": "True",
            },
        )
        self.env_patcher.start()
        self.service = MailService()

    def tearDown(self):
        self.env_patcher.stop()

    @patch("smtplib.SMTP")
    def test_send_mail_success(self, mock_smtp):
        # SMTPサーバーのモック
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # メール送信
        success = self.service.send_mail(
            to="to@example.com", subject="Test Subject", body="Test Body"
        )

        # 検証
        self.assertTrue(success)
        mock_smtp.assert_called_with("smtp.test.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_with("test@example.com", "password")
        # 送信元が MAIL_SMTP_USER になっていることを確認
        sent_msg = mock_server.send_message.call_args[0][0]
        self.assertEqual(sent_msg["From"], "test@example.com")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_mail_failure(self, mock_smtp):
        # SMTPサーバーのモック（エラーを発生させる）
        mock_smtp.side_effect = Exception("SMTP Error")

        # メール送信（例外が発生することを確認）
        with self.assertLogs("lib.mail.mail_service", level="ERROR") as cm:
            with self.assertRaises(MailSendError):
                self.service.send_mail(
                    to="to@example.com", subject="Test Subject", body="Test Body"
                )
        # ログが出力されていることを確認
        self.assertIn("Failed to send email", cm.output[0])

    @patch("smtplib.SMTP")
    def test_send_mail_missing_config(self, mock_smtp):
        # 必須設定（MAIL_SMTP_USER）を消去する
        with patch.dict("os.environ", {"MAIL_SMTP_USER": ""}):
            with self.assertRaises(ValueError) as cm:
                MailService()
            self.assertIn("MAIL_SMTP_USER", str(cm.exception))

    @patch("smtplib.SMTP")
    def test_send_mail_html(self, mock_smtp):
        # SMTPサーバーのモック
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        # HTMLメール送信
        success = self.service.send_mail(
            to="to@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body="<h1>Test Body</h1>",
        )

        # 検証
        self.assertTrue(success)
        # MIMEMultipart の中身までは深く検証しないが、send_message が呼ばれていることを確認
        mock_server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
