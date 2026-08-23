from django.contrib.auth import get_user_model


class UserRepository:
    """Django 標準Userに対する仮登録・本登録の永続化操作を提供するリポジトリ。"""

    @staticmethod
    def email_exists(email: str) -> bool:
        """指定メールアドレスのユーザーが既に存在するか返す。"""
        return get_user_model().objects.filter(email__iexact=email).exists()

    @staticmethod
    def create_inactive_user(email: str, password: str):
        """本登録前でログインできないユーザーを1件作成して返す。"""
        return get_user_model().objects.create_user(
            username=email,
            email=email,
            password=password,
            is_active=False,
        )

    @staticmethod
    def get_by_id(user_id: str):
        """主キーに対応するユーザーを返し、存在しなければNoneを返す。"""
        return get_user_model().objects.filter(pk=user_id).first()

    @staticmethod
    def activate(user) -> None:
        """指定ユーザーを本登録済みにし、ログインを許可する。"""
        user.is_active = True
        user.save(update_fields=["is_active"])

    @staticmethod
    def delete(user) -> None:
        """本登録メールを送れなかった仮登録ユーザーを削除する。"""
        user.delete()
