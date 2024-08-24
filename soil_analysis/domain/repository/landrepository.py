from soil_analysis.models import Land, Company, LandLedger


class LandRepository:
    def __init__(self, company: Company):
        self._company = company
        self._lands = Land.objects.filter(company=company)
        self.land_ledgers = LandLedger.objects.filter(land__in=self._lands)

    def read_land_ledgers(self, land: Land):
        return self.land_ledgers.filter(land=land)
