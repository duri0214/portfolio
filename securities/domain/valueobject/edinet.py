import datetime
from dataclasses import dataclass


@dataclass
class RequestData:
    SECURITIES_REPORT_AND_META_DATA = 2
    start_date: datetime.date
    end_date: datetime.date

    def __post_init__(self):
        if self.start_date > datetime.date.today():
            raise ValueError("start_date is in the future")
        if self.end_date > datetime.date.today():
            raise ValueError("end_date is in the future")
        if self.start_date > self.end_date:
            raise ValueError("start_date is later than end_date")

        self.doc_type = self.SECURITIES_REPORT_AND_META_DATA

        # Calculate day_list
        period = self.end_date - self.start_date
        self.day_list = []
        for d in range(int(period.days)):
            day = self.start_date + datetime.timedelta(days=d)
            self.day_list.append(day)
        self.day_list.append(self.end_date)


@dataclass
class CountingData:
    edinet_code: str | None = None
    filer_name_jp: str | None = None
    avg_salary: str | None = None
    avg_tenure_years: str | None = None
    avg_tenure_months: str | None = None
    avg_age_years: str | None = None
    avg_age_months: str | None = None
    number_of_employees: str | None = None

    @property
    def avg_tenure_years_combined(self) -> str | None:
        if self.avg_tenure_months:
            avg_tenure_decimal = round(int(self.avg_tenure_months) / 12, 1)
            avg_tenure = int(self.avg_tenure_years) + avg_tenure_decimal
            return str(avg_tenure)
        return self.avg_tenure_years

    @property
    def avg_age_years_combined(self) -> str | None:
        if self.avg_age_months:
            age_years_decimal = round(int(self.avg_age_months) / 12, 1)
            age_years = int(self.avg_age_years) + age_years_decimal
            return str(age_years)
        return self.avg_age_years
