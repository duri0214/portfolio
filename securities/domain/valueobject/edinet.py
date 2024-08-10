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
    """
    CountingData

    計数データを表すクラス

    Attributes:
        edinet_code (str | None): The EDINET code of the entity.
        filer_name_jp (str | None): The name of the entity in Japanese.
        avg_salary (str | None): The average salary of the entity.
        avg_tenure_years (str | None): The average tenure of employees in years.
        avg_tenure_months (str | None): The average tenure of employees in months.
        avg_age_years (str | None): The average age of employees in years.
        avg_age_months (str | None): The average age of employees in months.
        number_of_employees (str | None): The number of employees in the entity.

    Properties:
        avg_tenure_years_combined (str | None): 従業員の合計平均勤続年数。
            self.avg_tenure_months が存在する場合、平均在職期間の小数部分が計算されます。
            self.avg_tenure_months を 12 で割って、avg_tenure_years に加算します。
            結合された平均在職期間値の文字列表現を返します。

        avg_age_years_combined (str | None): 従業員の平均年齢を合計した年数。
            self.avg_age_months が指定されている場合、平均年齢の小数部分が計算されます。
            self.avg_age_months を 12 で割って、avg_age_years に加算します。
            結合された平均年齢値の文字列表現を返します。
    """

    edinet_code: str | None = None
    filer_name_jp: str | None = None
    avg_salary: int = 0
    avg_tenure_years: int = 0
    avg_tenure_months: int = 0
    avg_age_years: int = 0
    avg_age_months: int = 0
    number_of_employees: int = 0

    @property
    def avg_tenure_years_combined(self) -> float:
        if self.avg_tenure_months:
            avg_tenure_decimal = round(int(self.avg_tenure_months) / 12, 1)
            return int(self.avg_tenure_years) + avg_tenure_decimal
        return self.avg_tenure_years

    @property
    def avg_age_years_combined(self) -> float:
        if self.avg_age_months:
            age_years_decimal = round(int(self.avg_age_months) / 12, 1)
            return int(self.avg_age_years) + age_years_decimal
        return self.avg_age_years
