import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from usa_research.models import AssetPrice

# 対象資産の定義
# Stocks: ^GSPC (S&P 500 Index) - 1927年〜の超長期データ用
# Bonds: ^TYX (30Y Treasury Yield) - 1977年〜の利回りデータ
# Bills: BIL (短期国債 ETF) - 2007年〜
# Gold: GC=F (金先物) - 2000年〜
# Dollar: DX-Y.NYB (ドル指数) - 1971年〜
TICKERS = {
    "Stocks": "^GSPC",
    "Bonds": "^TYX",
    "Bills": "BIL",
    "Gold": "GC=F",
    "Dollar": "DX-Y.NYB",
}


class Command(BaseCommand):
    help = "Fetch historical asset prices (ETF and Indices) from Yahoo Finance and save to AssetPrice model"

    def add_arguments(self, parser):
        parser.add_argument(
            "--full",
            action="store_true",
            help="Fetch full historical data (max period). If not specified, fetches last 30 days.",
        )
        parser.add_argument(
            "--start",
            type=str,
            help="Start date (YYYY-MM-DD). If specified, overrides --full and default 30 days.",
        )
        parser.add_argument(
            "--end",
            type=str,
            help="End date (YYYY-MM-DD). Defaults to today.",
        )

    def handle(self, *args, **options):
        """
        Yahoo Finance から主要な資産クラスの歴史的価格データを取得し、AssetPrice モデルに保存します。

        取得対象の資産 (TICKERS):
        - Stocks: SPY (ETF), ^GSPC (S&P 500 Index)
        - Bonds: TLT (ETF), ^TYX (30Y Treasury Yield)
        - Bills: BIL (ETF)
        - Gold: GLD (ETF), GC=F (Futures)
        - Dollar: UUP (ETF), DX-Y.NYB (Index)

        処理のフロー:
        1. 引数の解析:
           - `--full`: 全期間 (max) のデータを取得。
           - `--start YYYY-MM-DD`: 指定された開始日からのデータを取得。
           - 指定がない場合: 直近30日間のデータをデフォルトで取得。
        2. yfinance (yf.download) を使用して、定義されたティッカーのデータを一括取得。
           - `Adj Close` (調整後終値) を優先的に使用し、存在しない場合は `Close` を使用。
           - 1日単位 (`interval="1d"`) のデータを取得。
        3. 取得データの正規化:
           - 単一ティッカー取得時と複数ティッカー取得時で pandas.DataFrame の構造が異なるため、
             一貫してマルチインデックス形式で扱えるよう補正。
        4. データベースへの保存:
           - 取得した各日付・各資産の価格をループ処理。
           - `AssetPrice.objects.update_or_create` を使用し、既存データがあれば更新、なければ新規作成。
           - 重複を避けつつ、最新の価格データに同期。

        利用シーン:
        - 初回構築時: `--full` または `--start 2000-01-01` 等を指定して過去データを一括投入。
        - 定期更新: 引数なしで実行し、直近30日分のデータを取得して最新状態を維持（月次バッチ想定）。
        """
        self.stdout.write("Fetching historical asset prices...")

        is_full = options.get("full")
        start_date_arg = options.get("start")
        end_date_arg = options.get("end")

        if start_date_arg:
            self.stdout.write(f"Mode: Custom range (Start: {start_date_arg})")
            start_date = start_date_arg
            period = None
        elif is_full:
            self.stdout.write("Mode: Full history")
            period = "max"
            start_date = None
        else:
            self.stdout.write("Mode: Last 30 days")
            period = None
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        tickers_list = list(TICKERS.values())

        # yf.downloadでデータを取得
        download_params = {
            "tickers": tickers_list,
            "interval": "1d",
            "group_by": "ticker",
            "progress": False,
        }

        if start_date:
            download_params["start"] = start_date
            if end_date_arg:
                download_params["end"] = end_date_arg
        else:
            download_params["period"] = period

        data = yf.download(**download_params)

        if data.empty:
            self.stderr.write("No data fetched from yfinance.")
            return

        # 1つしかティッカーがない場合、マルチインデックスの構造が変わる可能性があるため補正
        if len(tickers_list) == 1:
            ticker = tickers_list[0]
            # マルチインデックスにする
            data.columns = pd.MultiIndex.from_product([[ticker], data.columns])

        all_dates = data.index
        count = 0

        for date_ts in all_dates:
            date_only = date_ts.date()

            for asset_name, ticker in TICKERS.items():
                try:
                    # 調整後終値を取得
                    # Yahoo Financeのデータ構造を確認
                    # Adj Close が無い場合は Close を使用
                    col_name = (
                        "Adj Close" if "Adj Close" in data[ticker].columns else "Close"
                    )
                    val = data[ticker][col_name].loc[date_ts]
                    if pd.notna(val):
                        price = float(val)

                        # 保存処理 (update_or_create)
                        obj, created = AssetPrice.objects.update_or_create(
                            date=date_only, symbol=ticker, defaults={"price": price}
                        )
                        if created:
                            count += 1
                except (KeyError, IndexError):
                    continue

        self.stdout.write(
            self.style.SUCCESS(f"Successfully updated {count} new asset price records.")
        )
