from datetime import datetime

from django.conf import settings
from django.utils import timezone

from accounts.domain.repository.user import UserRepository
from accounts.domain.valueobject.activation import AccountActivationStatus
from accounts.tokens import account_activation_token
from lib.mail.mail_service import MailService


class RegistrationService:
    """仮登録ユーザーの作成と、認証済みユーザーへの切り替えを行うサービス。"""

    @staticmethod
    def create_pending_user(email: str, password: str):
        """メール認証前でログインできないユーザーを作成して返す。"""
        return UserRepository.create_inactive_user(email=email, password=password)

    @staticmethod
    def activate_user(user, token: str) -> AccountActivationStatus:
        """有効な認証トークンに対応する仮登録ユーザーを本登録へ切り替える。"""
        if not settings.ACCOUNT_EMAIL_SEND_ENABLED:
            return AccountActivationStatus.DISABLED

        status = account_activation_token.validate_token(user, token)
        if status == AccountActivationStatus.VALID:
            UserRepository.activate(user)
        return status


class RegistrationMailService:
    """本登録用メールを、明示的に有効化された環境だけで送信するサービス。"""

    @staticmethod
    def send_activation_mail(
        to: str, activation_url: str, activation_expires_at: datetime
    ) -> bool:
        """本登録URLと有効期限を送信し、送信無効時はSMTPへ接続せずFalseを返す。"""
        if not settings.ACCOUNT_EMAIL_SEND_ENABLED:
            return False

        expiration_text = timezone.localtime(activation_expires_at).strftime(
            "%Y年%m月%d日 %H:%M"
        )
        body = (
            "以下のURLを開いて、本登録を完了してください。"
            f"\n\n{activation_url}"
            f"\n\n本登録リンクの有効期限: {expiration_text}（日本時間）"
        )
        MailService().send_mail(
            to=to,
            subject="【ポートフォリオ】本登録のご案内",
            body=body,
        )
        return True
