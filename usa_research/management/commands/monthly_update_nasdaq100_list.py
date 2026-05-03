import os
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
import yfinance as yf
from django.conf import settings
from django.core.management.base import BaseCommand

from usa_research.models import Nasdaq100Company


class Command(BaseCommand):
    help = "Fetch NASDAQ100 components from Wikipedia"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # yfinanceのタイムゾーンキャッシュディレクトリに関するエラー(Issue #545)を回避するため、
        # プロジェクト内のディレクトリをキャッシュ先として指定する。
        # matplotlibの例に倣い、MEDIA_ROOT 内に配置する。
        cache_dir = os.path.join(settings.MEDIA_ROOT, "yfinance_cache")
        os.makedirs(cache_dir, exist_ok=True)
        yf.set_tz_cache_location(cache_dir)

    def handle(self, *args, **options):
        """
        NASDAQ100の構成銘柄とその業種情報を取得し、DBを更新します。

        処理の流れ:
        1. Wikipediaから構成銘柄一覧を取得 (fetch_from_wikipedia)
        2. yfinance にてセクター・業界情報を取得 (英語表記への統一)
        3. 取得した全データをループしてDBに保存 (Nasdaq100Companyモデル)

        実装上の注意点:
        - yfinanceのメタデータ取得(info)について:
            yfinanceの仕様上、セクター等のメタデータを一括で取得するAPIは存在せず、
            内部的には1銘柄ごとにHTTPリクエストが発生します。
            そのため、速度向上のための一括処理（yf.Tickers等）は採用せず、
            以下の理由から1件ずつのループ処理を行っています。
            1. 進捗の可視化: 100件超の取得には時間がかかるため、1件ずつログを出すことで実行状況を把握可能にする。
            2. 堅牢性: 特定の銘柄で取得エラーが発生しても、他の銘柄の更新を阻害しない。
        """
        self.stdout.write("Fetching NASDAQ100 components from Wikipedia...")

        companies = self.fetch_from_wikipedia()

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

    def fetch_from_wikipedia(self):
        """
        WikipediaのNasdaq-100ページから構成銘柄を取得します。
        """
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Wikipediaの constituents テーブルを取得
            dfs = pd.read_html(StringIO(response.text), attrs={"id": "constituents"})
            if not dfs:
                return []

            df = dfs[0]
            companies = []
            for _, row in df.iterrows():
                # Ticker, Company
                ticker = str(row["Ticker"]).strip()
                name = str(row["Company"]).strip()

                companies.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "sector": "",
                        "industry": "",
                        "source": "Wikipedia",
                    }
                )
            return companies
        except Exception as e:
            self.stderr.write(f"Failed to fetch data from Wikipedia: {e}")
            return []
