from abc import ABC, abstractmethod
from datetime import datetime

from django.db.models import QuerySet

from usa_research.domain.valueobject.market import Rss, RssEntry


class MarketAbstract(ABC):
    def __init__(self):
        # self.repository = MarketRepository() # まだRepositoryがないのでコメントアウト
        pass

    @abstractmethod
    def watchlist(self, **kwargs):
        pass

    @abstractmethod
    def calculate_transaction_fee(self, **kwargs):
        pass

    @abstractmethod
    def rss(self, json_data: dict) -> Rss:
        """
        Create a Rss instance from JSON object.
        Args:
            json_data: json dictionary.
        Returns:
            Instance of `Rss` dataclass.
        """
        pass


class UsaMarketDataProvider(MarketAbstract):

    def rss(self, json_data: dict) -> Rss:
        # RSSフィードの形式に合わせて調整が必要
        entries = []
        for item in json_data.get("entries", []):
            updated_str = item.get("updated") or item.get("published")
            updated = datetime.now()  # デフォルト
            if updated_str:
                try:
                    # 様々な形式に対応する必要があるかもしれない
                    updated = datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%S%z")
                except ValueError:
                    pass

            entries.append(
                RssEntry(
                    title=item.get("title", ""),
                    summary=item.get("summary", ""),
                    link=item.get("link", ""),
                    updated=updated,
                )
            )

        feed_updated_str = json_data.get("feed", {}).get("updated")
        feed_updated = datetime.now()
        if feed_updated_str:
            try:
                feed_updated = datetime.strptime(
                    feed_updated_str, "%Y/%m/%d %H:%M:%S %z"
                )
            except ValueError:
                pass

        return Rss(entries, feed_updated)

    def watchlist(self) -> QuerySet:
        pass

    @staticmethod
    def calculate_transaction_fee(price_without_fees: float) -> float:
        # 米国株の手数料計算ロジック（SBI証券など）
        # 約定代金の0.495%（税込）、最低0ドル、最大22ドル
        fee = price_without_fees * 0.00495
        if fee > 22:
            return 22.0
        return fee
