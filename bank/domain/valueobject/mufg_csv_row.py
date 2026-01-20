from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class MufgCsvRow:
    trade_date: date
    summary: str
    summary_detail: str
    payment_amount: Optional[int]
    deposit_amount: Optional[int]
    balance: int
    inout_type: Optional[str]
    memo: Optional[str]
    uncollected_flag: Optional[str]

    @property
    def year_month(self) -> int:
        return self.trade_date.year * 100 + self.trade_date.month

    def is_old_format_period(self) -> bool:
        return self.year_month <= 201303
