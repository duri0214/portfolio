from dataclasses import dataclass


@dataclass
class Company:
    edinet_code: str | None = None
    filer_name_jp: str | None = None
    industry_name: str | None = None
    salary_info: str | None = None
    service_years: str | None = None
    service_months: str | None = None
    age_years: str | None = None
    age_months: str | None = None
    number_of_employees: str | None = None

    @property
    def service_years_combined(self) -> str | None:
        if self.service_months:
            service_years_decimal = round(int(self.service_months) / 12, 1)
            service_years = int(self.service_years) + service_years_decimal
            return str(service_years)
        return self.service_years

    @property
    def age_years_combined(self) -> str | None:
        if self.age_months:
            age_years_decimal = round(int(self.age_months) / 12, 1)
            age_years = int(self.age_years) + age_years_decimal
            return str(age_years)
        return self.age_years

    def to_list(self) -> list[str | None]:
        return [
            self.edinet_code,
            self.filer_name_jp,
            self.industry_name,
            self.salary_info,
            self.service_years_combined,
            self.age_years_combined,
            self.number_of_employees,
        ]
