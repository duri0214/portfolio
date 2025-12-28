import requests
import yfinance as yf
from bs4 import BeautifulSoup
from datetime import datetime
from django.core.management.base import BaseCommand
from usa_research.models import Nasdaq100Company


class Command(BaseCommand):
    help = "Fetch NASDAQ100 components from Slickcharts"

    def handle(self, *args, **options):
        """
        NASDAQ100の構成銘柄とその業種情報を取得し、DBを更新します。

        処理の流れ:
        1. Slickchartsから構成銘柄一覧を取得 (fetch_from_slickcharts)
        2. yfinance にてセクター・業界情報を取得 (英語表記への統一)
        3. 取得した全データをループしてDBに保存 (Nasdaq100Companyモデル)
           - update_or_create を使用
        """
        self.stdout.write("Fetching NASDAQ100 components from Slickcharts...")

        companies = self.fetch_from_slickcharts()

        if not companies:
            self.stderr.write("No companies found.")
            return

        # yfinance でセクター情報を取得・統一（英語表記にするため）
        self.stdout.write("Unifying sector information via yfinance...")
        for item in companies:
            # yfinance で取得
            try:
                self.stdout.write(f"Fetching data for {item['ticker']} via yfinance...")
                ticker_info = yf.Ticker(item["ticker"]).info
                item["sector"] = ticker_info.get("sector", "Unknown")
                item["industry"] = ticker_info.get("industry", "")
            except Exception as e:
                self.stderr.write(f"Failed to fetch data for {item['ticker']}: {e}")
                if not item.get("sector"):
                    item["sector"] = "Unknown"

        # DB保存
        count = 0
        as_of = datetime.now().date()
        for item in companies:
            defaults = {
                "name": item["name"],
                "source": item["source"],
                "as_of": as_of,
                "sector": item.get("sector", "Unknown"),
                "industry": item.get("industry", ""),
            }

            obj, created = Nasdaq100Company.objects.update_or_create(
                ticker=item["ticker"], defaults=defaults
            )
            if created:
                count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {len(companies)} companies ({count} new)."
            )
        )

    def fetch_from_slickcharts(self):
        url = "https://www.slickcharts.com/nasdaq100"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            self.stderr.write(f"Failed to fetch data from Slickcharts: {e}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table")

        if not table:
            return []

        rows = table.find_all("tr")[1:]
        companies = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            # Slickcharts structure:
            # 0: Rank
            # 1: Company Name
            # 2: Symbol (Ticker)
            # 3: Weight

            name = cols[1].text.strip()
            ticker = cols[2].text.strip()

            companies.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "sector": "",  # Slickcharts has no sector info
                    "industry": "",
                    "source": "Slickcharts",
                }
            )
        return companies
