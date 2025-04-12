from shopping.models import Staff


class StaffRepository:
    """スタッフ関連のリポジトリ"""

    @staticmethod
    def get_all_staff() -> list:
        """すべてのスタッフを取得する"""
        return list(Staff.objects.all())

    @staticmethod
    def get_staff_by_id(staff_id: int) -> Staff | None:
        """スタッフIDからスタッフを取得する"""
        try:
            return Staff.objects.get(id=staff_id)
        except Staff.DoesNotExist:
            return None

    @staticmethod
    def save_staff(staff: Staff) -> Staff:
        """スタッフを保存する"""
        staff.save()
        return staff
