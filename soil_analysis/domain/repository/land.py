from django.db.models import QuerySet

from soil_analysis.models import Land, Company, LandLedger


class LandRepository:
    @staticmethod
    def find_land_by_id(land_id: int) -> Land:
        return Land.objects.get(pk=land_id)

    @staticmethod
    def find_land_ledgers_by_lands(lands: list[Land]) -> QuerySet:
        """
        複数の圃場に関連する台帳をまとめて取得する
        """
        return LandLedger.objects.filter(land__in=lands)

    @staticmethod
    def get_land_ledger_map(lands: list[Land]) -> dict[int, list[LandLedger]]:
        """
        圃場IDをキー、その圃場の台帳のリストを値とする辞書を返す
        """
        land_ledger_map = {}
        land_ledgers = LandRepository.find_land_ledgers_by_lands(lands)

        for land in lands:
            land_ledger_map[land.id] = list(land_ledgers.filter(land=land))

        return land_ledger_map

    @staticmethod
    def get_lands_by_company(company: Company = None) -> QuerySet:
        """
        会社に紐づく圃場を取得する
        会社が指定されていない場合は全圃場を返す
        """
        if company:
            return Land.objects.filter(company=company)
        return Land.objects.all()

    @staticmethod
    def get_land_to_ledgers_map(lands):
        """
        Landオブジェクトをキー、その圃場の台帳のQuerySetを値とする辞書を返す
        """
        land_ledger_map = {}
        land_ledgers = LandLedger.objects.filter(land__in=lands)

        for land in lands:
            land_ledger_map[land] = land_ledgers.filter(land=land)

        return land_ledger_map
