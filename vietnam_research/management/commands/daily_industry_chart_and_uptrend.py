import logging
import os
from glob import glob
from pathlib import Path

import pandas as pd
from PIL import Image
from django.core.management.base import BaseCommand
from matplotlib import pyplot as plt

from config.settings import BASE_DIR
from lib.log_service import LogService
from vietnam_research.domain.repository.vietkabu import IndustryRepository
from vietnam_research.domain.valueobject.vietkabu import IndustryGraphVO
from vietnam_research.models import Uptrend, Symbol, Market, Watchlist


def calc_price(price_for_several_days: pd.Series) -> dict:
    """
    数日間の価格のSeriesから、差を出す（例：14日前から直近までどちらにハネたか？）\n
    indexは0から始まるように下処理しておくこと

    Returns:
        dict: {'initial': 7.17, 'latest': 8.22, 'delta': 1.05}
    """
    initial_price = price_for_several_days.astype(float).iloc[0]
    latest_price = price_for_several_days.astype(float).iloc[-1]
    delta_price = round(latest_price - initial_price, 2)

    return {"initial": initial_price, "latest": latest_price, "delta": delta_price}


def formatted_text(code: str, slopes: list, passed: int, price: dict) -> str:
    initial = price.get("initial", "-")
    latest = price.get("latest", "-")
    delta = price.get("delta", "-")

    return f"{code}｜{slopes}, passed: {passed}, initial: {initial}, latest: {latest}, delta: {delta}"


class Command(BaseCommand):
    help = "industry uptrend"

    def handle(self, *args, **options):
        """
        Industryテーブルのuptrend

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """
        log_service = LogService("./result.log")

        plt.rcParams["font.family"] = ["IPAexGothic"]
        # make folder if not exists and delete old files and delete table data
        out_folder = (
            BASE_DIR.resolve() / "vietnam_research/static/vietnam_research/chart"
        )
        if not os.path.exists(out_folder):
            os.makedirs(out_folder)
        for filepath in glob(str(Path(out_folder) / "*.png")):
            log_service.write(f"Removing file: {filepath}")
            os.remove(filepath)
        Uptrend.objects.all().delete()

        # sbi tickers are plotting by matplotlib
        markets = Market.objects.filter(id__in=[1, 2])
        tickers = IndustryRepository.get_industry_tickers(markets)
        industry_records = IndustryRepository.get_symbol_details(markets)

        m_symbol = Symbol.objects.filter(market__in=markets).prefetch_related(
            "market", "ind_class"
        )
        watchlist_symbols = Watchlist.objects.all().values_list(
            "symbol__code", flat=True
        )

        days = [14, 7, 3]
        passed_records = []
        for ticker in tickers:
            closing_price = [
                x["closing_price"]
                for x in industry_records
                if x["symbol_code"] == ticker
            ]
            closing_price = pd.Series(closing_price, name="closing_price")
            plt.clf()

            # closing_price を使って、赤色の点としてプロット
            industry_graph_vo = IndustryGraphVO(ticker, closing_price)
            x_range, closing_price = industry_graph_vo.plot_values()
            plt.plot(x_range, closing_price, "ro")

            # 20日と40日の移動平均を計算・プロット
            for sma, color, label in zip(
                industry_graph_vo.plot_sma([20, 40]),
                ["r-", "g-"],
                ["20 Simple Moving Average", "40 Simple Moving Average"],
            ):
                plt.plot(x_range, sma, color, label=label)

            plt.legend(loc="upper left")
            reversed_labels = [str(i) for i in reversed(x_range)]
            plt.xticks(ticks=x_range, labels=reversed_labels)
            plt.ylabel("closing_price")
            plt.grid()

            slopes = []
            attempts = passed = 0
            price = {}
            for attempts, day in enumerate(days, start=1):
                if len(closing_price) < day:
                    continue
                slope, regression_range, regression_values = (
                    industry_graph_vo.plot_regression_slope(day)
                )
                slopes.append(slope)

                # 傾きが正の場合は 'passed' を増やし、傾きのラインを緑の点線でプロットする
                if slope > 0:
                    passed += 1
                plt.plot(regression_range, regression_values, "g--")
            if attempts == passed or ticker in watchlist_symbols:
                # 処理した株価の傾斜（線形回帰による）がdaysすべてにおいて正（つまり上昇傾向）だった場合
                recent_days_length = max(days)
                closing_price = closing_price[-recent_days_length:].reset_index(
                    drop=True
                )
                price = calc_price(closing_price)
                try:
                    passed_records.append(
                        Uptrend(
                            symbol=m_symbol.get(code=ticker),
                            stocks_price_oldest=price["initial"],
                            stocks_price_latest=price["latest"],
                            stocks_price_delta=price["delta"],
                        )
                    )
                except Symbol.DoesNotExist:
                    logging.critical(formatted_text(ticker, slopes, passed, price))

                # save png as w640, h480
                out_path = str(Path(out_folder) / f"{ticker}.png")
                plt.savefig(out_path)
                log_service.write(f"Saving file: {out_path}")
                # resize png as w250, h200
                Image.open(out_path).resize((250, 200), Image.LANCZOS).save(out_path)

            add_space = 2 if passed == len(days) else 0
            spaces = " " * add_space
            log_service.write(
                f"{spaces}{formatted_text(ticker, slopes, passed, price)}"
            )
        Uptrend.objects.bulk_create(passed_records)

        caller_file_name = Path(__file__).stem
        log_service.write(
            f"{caller_file_name} is done.(Number of tickers processed: {len(tickers)})"
        )
