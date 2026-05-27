from soil_analysis.models import SamplingOrder


class SamplingOrderRepository:
    """
    SamplingOrder関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_by_sampling_method(sampling_method_id: int) -> list[SamplingOrder]:
        """
        サンプリング手法IDに紐づくサンプリング順序を取得します

        Args:
            sampling_method_id: サンプリング手法のID

        Returns:
            list[SamplingOrder]: サンプリング順序のリスト
        """
        return list(
            SamplingOrder.objects.filter(
                sampling_method_id=sampling_method_id
            ).order_by("ordering")
        )
