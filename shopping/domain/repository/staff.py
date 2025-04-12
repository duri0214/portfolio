from shopping.models import Staff


class StaffRepository:
    """スタッフ関連のリポジトリ"""

    @staticmethod
    def get_all_staff() -> list:
        """すべてのスタッフを取得する"""
        return list(Staff.objects.all())
