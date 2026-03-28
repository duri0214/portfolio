from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RssEntry:
    """
    RSSフィードの個別の記事エントリーを保持する値オブジェクト。

    Attributes:
        title (str): 記事のタイトル
        summary (str): 記事の要約
        link (str): 記事へのリンクURL
        updated (datetime): 最終更新日時
    """

    title: str
    summary: str
    link: str
    updated: datetime


@dataclass(frozen=True)
class Rss:
    """
    RSSフィード全体（複数のエントリーと最終更新日時）を保持する値オブジェクト。

    Attributes:
        entries (list[RssEntry]): RSSエントリーのリスト
        updated (datetime): フィード全体の最終更新日時
    """

    entries: list[RssEntry]
    updated: datetime
