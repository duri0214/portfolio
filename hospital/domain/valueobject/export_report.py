from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from hospital.models import ElectionLedger


def convert_to_japanese_era(birth_date: date) -> str:
    year, month, day = birth_date.year, birth_date.month, birth_date.day
    if year > 2019 or (year == 2019 and month >= 5 and day >= 1):
        era_year = year - 2018
        era_name = "令和"
    elif year > 1989 or (year == 1989 and month >= 1 and day >= 8):
        era_year = year - 1988
        era_name = "平成"
    else:
        era_year = year - 1925
        era_name = "昭和"

    return f"{era_name} {era_year}.{month:02d}.{day:02d}"


class AbstractRow(ABC):
    @staticmethod
    @abstractmethod
    def get_field_names() -> list[str]:
        pass

    @abstractmethod
    def to_list(self) -> list[str]:
        pass


@dataclass
class BillingListRow(AbstractRow):
    ledger: ElectionLedger

    @property
    def address(self) -> str:
        return self.ledger.voter.userattribute.address

    @property
    def voter_name(self) -> str:
        return self.ledger.voter.username

    @property
    def date_of_birth(self) -> str:
        return convert_to_japanese_era(self.ledger.voter.userattribute.date_of_birth)

    @property
    def ward_name(self) -> str:
        return self.ledger.vote_ward.name

    @staticmethod
    def get_field_names() -> list[str]:
        return ["選挙人住所", "選挙人氏名", "生年月日", "病棟"]

    def to_list(self) -> list:
        return [self.address, self.voter_name, self.date_of_birth, self.ward_name]
