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
        return self.ledger.voter.userAttribute.address

    @property
    def voter_name(self) -> str:
        return self.ledger.voter.user.username

    @property
    def date_of_birth(self) -> str:
        return convert_to_japanese_era(self.ledger.voter.userAttribute.date_of_birth)

    @property
    def ward_name(self) -> str:
        return self.ledger.vote_ward.name

    @staticmethod
    def get_field_names() -> list[str]:
        return ["選挙人住所", "選挙人氏名", "生年月日", "病棟"]

    def to_list(self) -> list:
        return [self.address, self.voter_name, self.date_of_birth, self.ward_name]


@dataclass
class VotingManagementListRow(AbstractRow):
    ledger: ElectionLedger

    @property
    def address(self) -> str:
        return self.ledger.voter.userAttribute.address

    @property
    def voter_name(self) -> str:
        return self.ledger.voter.user.username

    @property
    def billing_method(self) -> str:
        return self.ledger.get_billing_method_display()

    @property
    def proxy_billing_request_date(self) -> str:
        if self.ledger.proxy_billing_request_date is None:
            return "XX.XX"
        else:
            return self.ledger.proxy_billing_request_date.strftime("%m.%d")

    @property
    def proxy_billing_date(self) -> str:
        if self.ledger.proxy_billing_date is None:
            return "XX.XX"
        else:
            return self.ledger.proxy_billing_date.strftime("%m.%d")

    @property
    def ballot_received_date(self) -> str:
        if self.ledger.ballot_received_date is None:
            return "XX.XX"
        else:
            return self.ledger.ballot_received_date.strftime("%m.%d")

    @property
    def vote_date(self) -> str:
        if self.ledger.vote_date is None:
            return "XX.XX"
        else:
            return self.ledger.vote_date.strftime("%m.%d")

    @property
    def vote_place(self) -> str:
        if self.ledger.vote_place is None:
            return "（未記入）"
        else:
            return self.ledger.vote_place.name

    @property
    def voter_witness(self) -> str:
        if self.ledger.vote_observer is None:
            return "（未記入）"
        else:
            return self.ledger.vote_observer.user.username

    @property
    def applied_for_proxy_voting(self) -> str:
        if self.ledger.applied_for_proxy_voting:
            return "有"
        else:
            return "無"

    @property
    def delivery_date(self) -> str:
        if self.ledger.delivery_date is None:
            return "XX.XX"
        else:
            return self.ledger.delivery_date.strftime("%m.%d")

    @staticmethod
    def get_field_names() -> list[str]:
        return [
            "選挙人住所",
            "選挙人氏名",
            "投票用紙の請求方法",
            "代理請求依頼日",
            "代理請求日",
            "投票用紙受領日",
            "投票日",
            "投票場所",
            "投票立会人",
            "代理投票申請の有無",
            "投票用紙送付日",
        ]

    def to_list(self) -> list:
        return [
            self.address,
            self.voter_name,
            self.billing_method,
            self.proxy_billing_request_date,
            self.proxy_billing_date,
            self.ballot_received_date,
            self.vote_date,
            self.vote_place,
            self.voter_witness,
            self.applied_for_proxy_voting,
            self.delivery_date,
        ]
