from dataclasses import dataclass
from datetime import datetime


@dataclass
class RssEntry:
    title: str
    summary: str
    link: str
    updated: datetime


@dataclass
class Rss:
    entries: list[RssEntry]
    updated: datetime
