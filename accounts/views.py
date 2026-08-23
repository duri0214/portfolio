from django.conf import settings
from django.shortcuts import render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View
from django.views.generic.edit import FormView

from accounts.domain.repository.user import UserRepository
from accounts.domain.service.registration import (
    RegistrationMailService,
    RegistrationService,
)
from accounts.domain.valueobject.activation import AccountActivationStatus
from accounts.forms import RegistrationForm
from accounts.tokens import account_activation_token
from lib.mail.mail_service import MailSendError


class RegistrationView(FormView):
    """1件の新規ユーザーを仮登録し、本登録用メールの送信結果を表示するビュー。"""

    template_name = "accounts/register.html"
    form_class = RegistrationForm

    def form_valid(self, form):
        """仮登録ユーザーを作成し、送信設定に応じて本登録メールを送る。"""
        user = RegistrationService.create_pending_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
        )
        activation_url = self._activation_url(user)

        try:
            mail_sent = RegistrationMailService.send_activation_mail(
                to=user.email,
                activation_url=activation_url,
            )
        except (MailSendError, ValueError):
            UserRepository.delete(user)
            return render(
                self.request,
                "accounts/registration_pending.html",
                {"mail_error": True},
            )

        return render(
            self.request,
            "accounts/registration_pending.html",
            {"mail_sent": mail_sent},
        )

    def _activation_url(self, user) -> str:
        """指定ユーザーの本登録URLを絶対URLで生成する。"""
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        path = reverse("accounts:activate", kwargs={"uidb64": uidb64, "token": token})
        return self.request.build_absolute_uri(path)


class AccountActivationView(View):
    """認証URLに対応する1件の仮登録ユーザーを本登録へ切り替えるビュー。"""

    template_name = "accounts/activation_result.html"

    def get(self, request, uidb64: str, token: str):
        """UIDとトークンを検証し、成功・期限切れ・無効の結果画面を返す。"""
        if not settings.ACCOUNT_EMAIL_SEND_ENABLED:
            return render(
                request,
                self.template_name,
                {"activation_status": AccountActivationStatus.DISABLED},
            )

        user = self._get_user(uidb64)
        activation_status = RegistrationService.activate_user(user, token)
        return render(
            request,
            self.template_name,
            {"activation_status": activation_status},
        )

    @staticmethod
    def _get_user(uidb64: str):
        """エンコード済みUIDから対象ユーザーを取得し、復元不能ならNoneを返す。"""
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
        except (TypeError, ValueError, OverflowError):
            return None
        return UserRepository.get_by_id(user_id)
