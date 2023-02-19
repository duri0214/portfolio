from abc import ABCMeta, abstractmethod

from django.db.models import QuerySet


class MarketAbstract(metaclass=ABCMeta):
    """各マーケットのための基底クラス"""
    @abstractmethod
    def watchlist(self) -> QuerySet:
        raise NotImplementedError()

    @abstractmethod
    def sbi_topics(self) -> str:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def calc_fee(price_without_fees: float) -> float:
        raise NotImplementedError()
