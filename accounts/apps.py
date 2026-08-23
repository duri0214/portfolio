from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """新規登録とメール認証を提供するアプリケーション設定。"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
