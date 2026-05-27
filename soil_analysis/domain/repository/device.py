from soil_analysis.models import Device


class DeviceRepository:
    """
    Device関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_all() -> list[Device]:
        """
        全てのデバイスを取得します

        Returns:
            list[Device]: デバイスのリスト
        """
        return list(Device.objects.all())

    @staticmethod
    def get_or_create_by_name(name: str) -> Device:
        """
        名前を指定してデバイスを取得、存在しない場合は作成します

        Args:
            name: デバイス名

        Returns:
            Device: デバイスインスタンス
        """
        device, _ = Device.objects.get_or_create(name=name)
        return device
