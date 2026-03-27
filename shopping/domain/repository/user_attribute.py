from shopping.models import UserAttribute


class UserAttributeRepository:
    """ユーザー属性（スタッフ・カスタマー）関連のリポジトリ"""

    @staticmethod
    def get_all_staff() -> list[UserAttribute]:
        """
        すべてのスタッフを取得する

        Returns:
            list[UserAttribute]: スタッフロールを持つ UserAttribute のリスト
        """
        return list(UserAttribute.objects.filter(role=UserAttribute.Role.STAFF))

    @staticmethod
    def get_all_customers() -> list[UserAttribute]:
        """
        すべてのカスタマーを取得する

        Returns:
            list[UserAttribute]: カスタマーロールを持つ UserAttribute のリスト
        """
        return list(UserAttribute.objects.filter(role=UserAttribute.Role.CUSTOMER))
