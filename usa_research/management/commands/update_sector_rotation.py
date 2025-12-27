import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from usa_research.models import Sector, SectorDailySnapshot

SECTORS = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
BENCHMARK = "SPY"


class Command(BaseCommand):
    help = "Fetch US sector ETF data and update sector rotation table"

    def handle(self, *args, **options):
        """
        米国株セクターETFのデータを取得し、セクターローテーション計数表を更新します。

        処理の流れ:
        1. セクター情報（GICS 11セクター）の初期化
        2. yfinanceを使用してセクターETFとベンチマーク（SPY）の過去120日分のデータを取得
        3. 各ETFの20日リターンを計算
        4. ベンチマークとの相対比較（Relative Strength: RS）を計算
        5. RSに基づくセクター内ランクを計算
        6. 5営業日前との比較（ΔRS, ΔRank）を計算
        7. 計算結果をSectorDailySnapshotモデルに保存（信号機ルールの適用を含む）
        """
        self.stdout.write("Updating sector rotation data...")

        # 1. セクター情報の初期化
        for name, symbol in SECTORS.items():
            Sector.objects.get_or_create(name=name, symbol=symbol)

        # 2. データの取得 (直近60営業日以上が必要なので、余裕を持って90日分取得)
        symbols = list(SECTORS.values()) + [BENCHMARK]
        end_date = datetime.now()
        start_date = end_date - timedelta(days=120)

        data = yf.download(
            symbols,
            start=start_date,
            end=end_date,
            interval="1d",
            group_by="ticker",
        )

        if data.empty:
            self.stderr.write("No data fetched from yfinance.")
            return

        # 'Adj Close' または 'Adj_Close' を取り出す
        adj_close_data = pd.DataFrame()
        for symbol in symbols:
            if symbol in data.columns.levels[0]:
                ticker_data = data[symbol]
                if "Adj Close" in ticker_data.columns:
                    adj_close_data[symbol] = ticker_data["Adj Close"]
                elif "Adj_Close" in ticker_data.columns:
                    adj_close_data[symbol] = ticker_data["Adj_Close"]
                elif "Close" in ticker_data.columns:
                    adj_close_data[symbol] = ticker_data["Close"]
                else:
                    self.stdout.write(f"Warning: No close data for {symbol}")
            else:
                self.stdout.write(f"Warning: No data for {symbol}")

        if adj_close_data.empty:
            self.stderr.write("No Adj Close data available.")
            return

        # 欠損値補完
        adj_close_data = adj_close_data.ffill()

        # 3. リターンの計算 (20日リターン)
        returns_20d = adj_close_data.pct_change(20, fill_method=None)

        # 4. RS (Relative Strength) の計算
        # RS_20d = (セクターETFの20日リターン − SPYの20日リターン) * 100 (%)
        rs_20d = returns_20d.copy()
        for symbol in SECTORS.values():
            rs_20d[symbol] = (returns_20d[symbol] - returns_20d[BENCHMARK]) * 100

        # SPYの列は不要なので削除
        rs_20d = rs_20d.drop(columns=[BENCHMARK])

        # 5. Rank の計算 (RS_20d を全11セクターで降順ソート)
        rank_df = rs_20d.rank(axis=1, ascending=False)

        # 6. ΔRS (5日) と ΔRank (5日) の計算
        # ΔRS_5d = RS_20d(today) − RS_20d(5営業日前)
        # ΔRank_5d = Rank(today) − Rank(5営業日前)
        rs_slope_5d = rs_20d.diff(5)
        rank_delta_5d = rank_df.diff(5)

        # 7. データの保存
        # 直近の営業日から順に保存 (データがある分だけ)
        dates = rs_20d.index[25:]  # 十分なデータがあるところから開始

        for date in dates:
            date_only = date.date()

            # 各セクターのデータを保存
            for name, symbol in SECTORS.items():
                sector = Sector.objects.get(symbol=symbol)

                try:
                    rs_val = rs_20d.loc[date, symbol]
                    rs_slope = rs_slope_5d.loc[date, symbol]
                    rank_val = int(rank_df.loc[date, symbol])
                    rank_delta = int(rank_delta_5d.loc[date, symbol])

                    if (
                        pd.isna(rs_val)
                        or pd.isna(rs_slope)
                        or pd.isna(rank_val)
                        or pd.isna(rank_delta)
                    ):
                        continue

                    # 信号機ルールの適用
                    signal = self._calculate_signal(rs_val, rs_slope, rank_delta)

                    SectorDailySnapshot.objects.update_or_create(
                        date=date_only,
                        sector=sector,
                        defaults={
                            "rs_20d": rs_val,
                            "rs_slope_5d": rs_slope,
                            "rank": rank_val,
                            "rank_delta_5d": rank_delta,
                            "signal": signal,
                        },
                    )
                except KeyError:
                    continue

        self.stdout.write(
            self.style.SUCCESS("Successfully updated sector rotation data")
        )

    @staticmethod
    def _calculate_signal(rs_20d, rs_slope_5d, rank_delta_5d):
        """
        計算された指標に基づき、信号機（Signal）の色を判定します。

        判定基準:
        - Green (出遅れからの反発):
            市場平均より弱く（RS < 0）、勢いが改善（ΔRS > 0）しており、かつ順位が2位以上上昇（ΔRank <= -2）している場合。
        - Yellow (勢い改善中):
            5営業日前よりもRSが改善（ΔRS > 0）している場合。
        - Red (過熱からの失速):
            市場平均より強く（RS > 0）、勢いが衰え（ΔRS < 0）ており、かつ順位が2位以上下落（ΔRank >= 2）している場合。
        - None: 上記以外。
        """
        # Green: RS_20d < 0 かつ ΔRS_5d > 0 かつ ΔRank_5d ≤ -2
        if rs_20d < 0 < rs_slope_5d and rank_delta_5d <= -2:
            return "Green"
        # Yellow: ΔRS_5d > 0
        elif rs_slope_5d > 0:
            return "Yellow"
        # Red: RS_20d > 0 かつ ΔRS_5d < 0 かつ ΔRank_5d ≥ 2
        elif rs_slope_5d < 0 < rs_20d and rank_delta_5d >= 2:
            return "Red"
        else:
            return "None"
