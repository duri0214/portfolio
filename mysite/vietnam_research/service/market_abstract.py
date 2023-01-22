from abc import ABCMeta, abstractmethod

from django.db.models import QuerySet
from sqlalchemy import create_engine


class MarketAbstract(metaclass=ABCMeta):
    """各マーケットのための基底クラス"""
    _con_str = 'mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1'
    _con = create_engine(_con_str, echo=False).connect()

    @abstractmethod
    def watchlist(self) -> QuerySet:
        raise NotImplementedError()

    @abstractmethod
    def uptrends(self):
        raise NotImplementedError()

    @abstractmethod
    def sbi_topics(self) -> str:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def calc_fee(price_without_fees: float) -> float:
        raise NotImplementedError()
