from dataclasses import dataclass


@dataclass
class Company:
    def __init__(self):
        self.edinet_code = None
        self.filer_name_jp = None
        self.industry_name = None
        self.salary_info = None
        self.service_years = None
        self.service_months = None
        self.age_years = None
        self.age_months = None
        self.number_of_employees = None

    @property
    def service_years_combined(self) -> str:
        if self.service_months:
            service_years_decimal = round(int(self.service_months) / 12, 1)
            service_years = int(self.service_years) + service_years_decimal
            return str(service_years)
        return self.service_years

    @property
    def age_years_combined(self) -> str:
        if self.age_months:
            age_years_decimal = round(int(self.age_months) / 12, 1)
            age_years = int(self.age_years) + age_years_decimal
            return str(age_years)
        return self.age_years

    def to_list(self) -> list[str]:
        return [
            self.edinet_code,
            self.filer_name_jp,
            self.industry_name,
            self.salary_info,
            self.service_years_combined,
            self.age_years_combined,
            self.number_of_employees,
        ]


@dataclass
class EdinetIndustry:
    edinet_code: str
    industry_name: str
