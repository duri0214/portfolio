from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int

from accounts.domain.valueobject.activation import AccountActivationStatus


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """仮登録ユーザーを一度だけ本登録できる期限付きトークンを生成・検証する。"""

    def _make_hash_value(self, user, timestamp: int) -> str:
        """ログイン可否を署名に含め、本登録完了後に同じURLを無効化する。"""
        return f"{user.pk}{user.password}{timestamp}{user.email}{user.is_active}"

    def validate_token(self, user, token: str) -> AccountActivationStatus:
        """トークンを検証し、有効・期限切れ・無効の状態を返す。"""
        if not user or not token:
            return AccountActivationStatus.INVALID

        try:
            ts_b36, _ = token.split("-")
            timestamp = base36_to_int(ts_b36)
        except ValueError:
            return AccountActivationStatus.INVALID

        for secret in [self.secret, *self.secret_fallbacks]:
            expected_token = self._make_token_with_timestamp(user, timestamp, secret)
            if constant_time_compare(expected_token, token):
                break
        else:
            return AccountActivationStatus.INVALID

        elapsed_seconds = self._num_seconds(self._now()) - timestamp
        if elapsed_seconds > settings.ACCOUNT_ACTIVATION_TIMEOUT:
            return AccountActivationStatus.EXPIRED
        return AccountActivationStatus.VALID


account_activation_token = AccountActivationTokenGenerator()
