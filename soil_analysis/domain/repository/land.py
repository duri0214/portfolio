from soil_analysis.models import Land


class LandRepository:
    @staticmethod
    def find_land_by_id(land_id: int) -> Land:
        return Land.objects.get(pk=land_id)

    @staticmethod
    def exists_by_name(name: str) -> bool:
        """
        名前を指定して圃場が存在するか確認します

        Args:
            name: 圃場名

        Returns:
            bool: 存在する場合はTrue
        """
        return Land.objects.filter(name=name).exists()

    @staticmethod
    def get_land_to_ledgers_map(lands: list[Land]) -> dict[int, list]:
        """
        圃場ごとの帳簿マップを取得します

        Args:
            lands: 圃場のリスト

        Returns:
            dict[int, list]: 圃場IDをキー、帳簿のリストを値とする辞書
        """
        from soil_analysis.models import LandLedger

        ledgers = (
            LandLedger.objects.filter(land__in=lands)
            .select_related("land_period")
            .order_by("-land_period__year", "-land_period__name")
        )

        land_to_ledgers = {land.id: [] for land in lands}
        for ledger in ledgers:
            land_to_ledgers[ledger.land_id].append(ledger)

        return land_to_ledgers
