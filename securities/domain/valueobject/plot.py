import datetime
from dataclasses import dataclass


@dataclass
class RequestData:
    start_date: datetime.date
    end_date: datetime.date

    def __post_init__(self):
        if self.start_date > datetime.date.today():
            raise ValueError("start_date is in the future")
        if self.end_date > datetime.date.today():
            raise ValueError("end_date is in the future")
        if self.start_date > self.end_date:
            raise ValueError("start_date is later than end_date")
