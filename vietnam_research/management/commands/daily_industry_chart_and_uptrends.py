import logging
import os
from glob import glob
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from django.core.management.base import BaseCommand
from django.db.models import F
from matplotlib import pyplot as plt

from config.settings import BASE_DIR
from vietnam_research.domain.service.log import LogService
from vietnam_research.models import Industry, Uptrends, Symbol


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

        # make folder if not exists and delete old files and delete table data
        out_folder = (
            BASE_DIR.resolve() / "vietnam_research/static/vietnam_research/chart"
        )
        if not os.path.exists(out_folder):
            os.makedirs(out_folder)
        [os.remove(filepath) for filepath in glob(str(Path(out_folder) / "*.png"))]
        Uptrends.objects.all().delete()  # TODO: 多分indexがリセットされないのでTRUNCATEにしたい

        # all tickers are plotting by matplotlib
        industry_records = (
            Industry.objects.filter(symbol__market__in=[1, 2])
            .filter(symbol__sbi__isnull=False)
            .distinct()
            .values("symbol__code")
        )
        tickers = [x["symbol__code"] for x in industry_records]

        # only stocks handled by SBI Securities
        industry_records = (
            Industry.objects.filter(symbol__market__in=[1, 2])
            .filter(symbol__sbi__isnull=False)
            .annotate(
                market_code=F("symbol__market__code"),
                symbol_code=F("symbol__code"),
            )
            .order_by(
                "symbol__ind_class__industry1",
                "symbol__ind_class__industry2",
                "symbol",
                "recorded_date",
            )
            .values(
                "symbol__ind_class__industry1",
                "symbol__ind_class__industry2",
                "market_code",
                "symbol_code",
                "recorded_date",
                "closing_price",
            )
        )

        m_symbol = Symbol.objects.filter(market__in=[1, 2]).prefetch_related(
            "market", "ind_class"
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
            x_range = range(len(closing_price))
            plt.plot(x_range, closing_price, "ro")
            plt.plot(
                x_range,
                closing_price.rolling(20).mean(),
                "r-",
                label="20 Simple Moving Average",
            )
            plt.plot(
                x_range,
                closing_price.rolling(40).mean(),
                "g-",
                label="40 Simple Moving Average",
            )
            plt.legend(loc="upper left")
            plt.ylabel("closing_price")
            plt.grid()

            slopes = []
            attempts = passed = 0
            price = {}
            for day in days:
                if len(closing_price) < day:
                    continue
                attempts += 1
                # e.g. 3 days ago to today, 7 days ago to today, 14 days ago to today
                closing_price_in_period = closing_price[-day:].astype(float)
                x_range = range(len(closing_price_in_period))
                # specific array for linear regression in numpy
                specific_array = np.array([x_range, np.ones(len(x_range))]).T
                # calculate the line slope
                slope, intercept = np.linalg.lstsq(
                    specific_array, closing_price_in_period, rcond=-1
                )[0]
                slopes.append(slope)
                # the line slope is positive?
                if slope > 0:
                    passed += 1
                # plot the slope line with green dotted lines
                date_back_to = len(closing_price) - day
                regression_range = range(date_back_to, date_back_to + day)
                plt.plot(regression_range, (slope * x_range + intercept), "g--")
                # save png as w640, h480
                out_path = str(Path(out_folder) / f"{ticker}.png")
                plt.savefig(out_path)
                # resize png as w250, h200
                Image.open(out_path).resize((250, 200), Image.LANCZOS).save(out_path)
            if attempts == passed:
                # e.g. 14 days ago to today
                closing_price = closing_price[-max(days) :].reset_index(drop=True)
                price = calc_price(closing_price)
                try:
                    passed_records.append(
                        Uptrends(
                            symbol=m_symbol.get(code=ticker),
                            stocks_price_oldest=price["initial"],
                            stocks_price_latest=price["latest"],
                            stocks_price_delta=price["delta"],
                        )
                    )
                except Symbol.DoesNotExist:
                    logging.critical(formatted_text(ticker, slopes, passed, price))

            logging.info(formatted_text(ticker, slopes, passed, price))
        Uptrends.objects.bulk_create(passed_records)

        caller_file_name = Path(__file__).stem
        log_service = LogService("./result.log")
        log_service.write(f"{caller_file_name} is done.({len(tickers)})")

        # TODO: パフォーマンスカイゼンして！原因はsymbolマスタにtickerかぶり（社名変更）があるため。バッチの新規Symbol取り込み部分もなおす
        # TODO: -400日が何月何日なのか表示
