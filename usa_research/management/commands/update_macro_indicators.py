import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from usa_research.models import MacroIndicator

TICKERS = {
    "ism_pmi": "NAPM",  # NOTE: NAPM (ISM PMI) might be unavailable on Yahoo Finance recently
    "us_10y_yield": "^TNX",
    "vix": "^VIX",
}


class Command(BaseCommand):
    help = "Fetch macro indicators (ISM, US10Y, VIX) from Yahoo Finance and save to MacroIndicator model"

    def handle(self, *args, **options):
        """
        Yahoo Finance から主要なマクロ指標を取得し、MacroIndicator モデルに保存します。

        取得対象の指標:
        - ISM 製造業景気指数 (ISM PMI): ティッカー 'NAPM'
          - 製造業の景況感を示す指標。50を上回ると景気拡大、下回ると景気後退。
          - 月次指標だが、Yahoo Finance では日次形式で配信される。
        - 米国10年国債利回り (US 10Y Yield): ティッカー '^TNX'
          - 長期金利の代表的な指標。
        - VIX 指数 (Volatility Index): ティッカー '^VIX'
          - 「恐怖指数」。市場の変動性予測を示す。

        処理のフロー:
        1. 直近30日間のデータを yfinance 経由で一括取得。
        2. 取得したデータの日付（営業日）ごとにループ処理。
        3. 指定した日付の MacroIndicator レコードを取得、または存在しない場合は新規作成 (get_or_create)。
        4. 各フィールド（ism_pmi, us_10y_yield, vix）について：
           - 現在の値が NULL、または取得した値と差異がある場合のみ更新。
        5. 更新があった場合のみ、データベースに保存 (save)。

        注意:
        - 'NAPM' (ISM) は、Yahoo Finance の仕様変更によりデータが取得できない場合があります。
        - 既にデータが存在する日付に対しても、欠損値の補完や値の更新を行うため、
          後から発表される月次データ（ISMなど）を既存の日次レコード（VIXなど）にマージすることが可能です。
        """
        self.stdout.write("Fetching macro indicators...")

        # 過去30日分のデータを取得（ISMが月次なので余裕を持つが、基本は日次バッチ）
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # yf.downloadで一括取得
        data = yf.download(
            list(TICKERS.values()),
            start=start_date,
            end=end_date,
            interval="1d",
            group_by="ticker",
        )

        if data.empty:
            self.stderr.write("No data fetched from yfinance.")
            return

        # 日付ごとに処理
        # yfinanceのデータはインデックスがDatetimeIndex
        all_dates = data.index

        for date_ts in all_dates:
            date_only = date_ts.date()

            # 各指標の値を取得
            row_data = {}
            for field_name, ticker in TICKERS.items():
                try:
                    # group_by="ticker" の場合、columnsは (Ticker, Field) のマルチインデックス
                    val = data[ticker]["Close"].loc[date_ts]
                    if pd.notna(val):
                        row_data[field_name] = float(val)
                except KeyError:
                    continue

            if not row_data:
                continue

            # 保存処理
            obj, created = MacroIndicator.objects.get_or_create(date=date_only)

            # 更新ルール:
            # - 値が変わっていなければ更新しない (Djangoのsaveはデフォルトでフィールド比較しないが、今回は手動で制御)
            # - NULL の項目のみ補完、または値が異なる場合に更新
            updated = False
            for field, value in row_data.items():
                current_val = getattr(obj, field)
                if current_val is None or abs(current_val - value) > 1e-6:
                    setattr(obj, field, value)
                    updated = True

            if updated:
                obj.save()
                status = "Created" if created else "Updated"
                self.stdout.write(f"[{date_only}] {status}: {row_data}")
            else:
                self.stdout.write(f"[{date_only}] No changes.")

        self.stdout.write(self.style.SUCCESS("Successfully updated macro indicators"))
