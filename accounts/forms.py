from django import forms
from django.contrib.auth.password_validation import validate_password

from accounts.domain.repository.user import UserRepository


class RegistrationForm(forms.Form):
    """メールアドレスとパスワードで仮登録するための入力フォーム。"""

    email = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}
        ),
    )
    password1 = forms.CharField(
        label="パスワード",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="パスワード（確認）",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
    )

    def clean_email(self) -> str:
        """未登録のメールアドレスを小文字へ正規化して返す。"""
        email = self.cleaned_data["email"].lower()
        if UserRepository.email_exists(email):
            raise forms.ValidationError("このメールアドレスはすでに登録されています。")
        return email

    def clean(self) -> dict[str, str]:
        """一致するパスワードが Django のパスワード規約を満たすか検証する。"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "確認用パスワードが一致しません。")
            return cleaned_data

        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data
