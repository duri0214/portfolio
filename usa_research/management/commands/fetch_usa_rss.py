import feedparser
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from time import mktime
from usa_research.models import RssSource, RssFeed


class Command(BaseCommand):
    """
    RSSフィードを取得してデータベースに保存するカスタムコマンド。

    【設計思想】
    1. 表示速度の向上:
       ページ表示のたびに外部RSSへアクセスすると遅延が発生するため、事前に取得してDBに保存します。
    2. API負荷と制限の回避:
       短時間の頻繁なアクセスによるアクセス制限（BAN）を回避します。
    3. 既存アプリとの統一性:
       プロジェクトの他の機能（ベトナム株データ等）と同様、日次バッチ（cron等）での運用を前提としています。
    """

    help = "Fetch RSS feeds from sources"

    def handle(self, *args, **options):
        # 初回実行時などのためにソースを登録（必要に応じて）
        self.init_sources()

        sources = RssSource.objects.filter(is_active=True)
        for source in sources:
            self.stdout.write(f"Fetching {source.name}...")
            feed = feedparser.parse(source.url)

            count = 0
            for entry in feed.entries:
                # 日付の取得
                published_at = timezone.now()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed)
                    )
                    published_at = timezone.make_aware(published_at)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))
                    published_at = timezone.make_aware(published_at)

                # 重複チェック（linkをユニークキーとする）
                if not RssFeed.objects.filter(link=entry.link).exists():
                    RssFeed.objects.create(
                        source=source,
                        title=entry.get("title", "No Title")[:500],
                        summary=(
                            entry.get("summary", "")
                            if hasattr(entry, "summary")
                            else ""
                        ),
                        link=entry.link,
                        published_at=published_at,
                    )
                    count += 1

            source.last_fetched_at = timezone.now()
            source.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully fetched {count} new entries from {source.name}"
                )
            )

    @staticmethod
    def init_sources():
        default_sources = [
            ("MarketWatch", "https://www.marketwatch.com/site/rss", "Markets"),
            (
                "Bloomberg Markets",
                "https://feeds.bloomberg.com/markets/news.rss",
                "Markets",
            ),
            (
                "Bloomberg Politics",
                "https://feeds.bloomberg.com/politics/news.rss",
                "Politics",
            ),
            (
                "Bloomberg Technology",
                "https://feeds.bloomberg.com/technology/news.rss",
                "Technology",
            ),
            (
                "Bloomberg Wealth",
                "https://feeds.bloomberg.com/wealth/news.rss",
                "Wealth",
            ),
            (
                "Bloomberg Economics",
                "https://feeds.bloomberg.com/economics/news.rss",
                "Economics",
            ),
            (
                "Bloomberg Industries",
                "https://feeds.bloomberg.com/industries/news.rss",
                "Industries",
            ),
            ("Bloomberg Green", "https://feeds.bloomberg.com/green/news.rss", "Green"),
            ("WSJ Japan", "https://jp.wsj.com/news/rss-news-and-feeds", "Markets"),
            ("CNBC", "https://www.cnbc.com/rss-feeds/", "Markets"),
            (
                "S&P Global",
                "https://www.spglobal.com/commodityinsights/en/market-insights/rss-feed",
                "Markets",
            ),
        ]

        for name, url, category in default_sources:
            RssSource.objects.get_or_create(
                url=url, defaults={"name": name, "category": category}
            )
