import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# .env ファイルを読み込む
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class MailService:
    """
    SMTPを使用してメールを送信するスタンドアロンサービス。
    Djangoなどのフレームワークに依存せず、lib/mail/.env の設定を使用して動作します。
    """

    def __init__(self):
        """
        環境変数から設定を読み込み、初期化します。
        """
        self.host = os.getenv("MAIL_SMTP_HOST")
        self.port = int(os.getenv("MAIL_SMTP_PORT", 587))
        self.user = os.getenv("MAIL_SMTP_USER")
        self.password = os.getenv("MAIL_SMTP_PASSWORD")
        self.use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
        self._validate_config()

    def _validate_config(self):
        """
        SMTP設定が不完全な場合に例外を発生させます。
        """
        missing_envs = []
        if not self.host:
            missing_envs.append("MAIL_SMTP_HOST")
        if not self.port:
            missing_envs.append("MAIL_SMTP_PORT")
        if not self.user:
            missing_envs.append("MAIL_SMTP_USER")
        if not self.password:
            missing_envs.append("MAIL_SMTP_PASSWORD")

        if missing_envs:
            raise ValueError(
                f"SMTP configuration is incomplete. Missing required environment variable(s): {', '.join(missing_envs)}"
            )

    def send_mail(
        self, to: str, subject: str, body: str, html_body: str = None
    ) -> bool:
        """
        メールを送信します。

        Args:
            to (str): 宛先メールアドレス
            subject (str): 件名
            body (str): 本文（プレーンテキスト）
            html_body (str, optional): 本文（HTML）。指定された場合はマルチパートで送信。

        Returns:
            bool: 送信成功なら True
        """
        # メッセージの作成
        msg = MIMEMultipart("alternative")
        msg["From"] = self.user
        msg["To"] = to
        msg["Subject"] = subject

        # プレーンテキストパートの追加
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # HTMLパートの追加（もしあれば）
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            # SMTPサーバーに接続
            server = smtplib.SMTP(self.host, self.port)
            if self.use_tls:
                server.starttls()

            server.login(self.user, self.password)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False


if __name__ == "__main__":
    """
    スクリプト単体での動作確認。
    lib/mail/ フォルダ内で実行してください。
    """
    print("Testing MailService...")
    try:
        service = MailService()
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

    test_to = service.user  # 自分宛にテスト
    test_subject = "Test Mail from MailService"
    test_body = "This is a test email sent from the standalone MailService."

    success = service.send_mail(test_to, test_subject, test_body)
    if success:
        print(f"Test email sent successfully to {test_to}")
    else:
        print("Failed to send test email.")
