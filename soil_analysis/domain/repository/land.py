from soil_analysis.models import Land, LandLedger


class LandRepository:
    @staticmethod
    def find_land_by_id(land_id: int) -> Land:
        return Land.objects.get(pk=land_id)

    @staticmethod
    def get_land_to_ledgers_map(land_list: list[Land]):
        """
        Landオブジェクトをキー、その圃場の台帳のQuerySetを値とする辞書を返す
        """
        land_ledger_map = {}
        land_ledgers = LandLedger.objects.filter(land__in=land_list)

        for land in land_list:
            land_ledger_map[land] = land_ledgers.filter(land=land)

        return land_ledger_map
