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
from mysite.settings import BASE_DIR
from vietnam_research.models import Industry, DailyUptrends, Symbol
from vietnam_research.service import log_writter


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

    return {'initial': initial_price, 'latest': latest_price, 'delta': delta_price}


def formatted_text(code: str, slopes: list, passed: int, price: dict) -> str:
    initial = price.get('initial', '-')
    latest = price.get('latest', '-')
    delta = price.get('delta', '-')

    return f"{code}｜{slopes}, passed: {passed}, initial: {initial}, latest: {latest}, delta: {delta}"


class Command(BaseCommand):
    help = 'industry uptrends'

    def handle(self, *args, **options):
        """
        Industryテーブルのuptrends

        See Also: https://docs.djangoproject.com/en/4.2/howto/custom-management-commands/
        See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        """

        # make folder if not exists and delete old files and delete table data
        out_folder = BASE_DIR.resolve() / 'vietnam_research/static/vietnam_research/chart'
        if not os.path.exists(out_folder):
            os.makedirs(out_folder)
        [os.remove(filepath) for filepath in glob(str(Path(out_folder) / '*.png'))]
        DailyUptrends.objects.all().delete()  # TODO: 多分indexがリセットされないのでTRUNCATEにしたい

        # only stocks handled by SBI Securities
        industry_records = Industry.objects \
            .filter(symbol__market__in=[1, 2]) \
            .filter(symbol__sbi__isnull=False) \
            .annotate(
                market_code=F('symbol__market__code'),
                symbol_code=F('symbol__code'),
            ) \
            .order_by('symbol__ind_class__industry1', 'symbol__ind_class__industry2', 'symbol', 'recorded_date') \
            .values('symbol__ind_class__industry1', 'symbol__ind_class__industry2', 'market_code', 'symbol_code',
                    'recorded_date', 'closing_price')

        m_symbol = Symbol.objects.filter(market__in=[1, 2]).prefetch_related('market', 'ind_class')

        # TODO: 処理対象レコードのシンボルが新規だった場合にm_symbolと突合して登録

        # all tickers are plotting by matplotlib
        symbol_codes = [x['symbol__code'] for x in
                        Industry.objects.filter(symbol__market__in=[1, 2]).filter(symbol__sbi__isnull=False).distinct().values('symbol__code')]
        days = [14, 7, 3]
        passed_records = []
        for symbol_code in symbol_codes:
            values = pd.DataFrame([x for x in industry_records if x['symbol_code'] == symbol_code])  # TODO: a_company_recordsに名称変更する
            plt.clf()
            plt.plot(range(len(values)), values['closing_price'], "ro")
            plt.plot(range(len(values)), values['closing_price'].rolling(20).mean(), "r-", label="20 Simple Moving Average")
            plt.plot(range(len(values)), values['closing_price'].rolling(40).mean(), "g-", label="40 Simple Moving Average")
            plt.legend(loc="upper left")
            plt.ylabel('closing_price')
            plt.grid()

            slopes = []
            attempts = passed = 0
            price = {}
            for day in days:
                if len(values) < day:
                    continue
                attempts += 1
                # e.g. 3 days ago to today, 7 days ago to today, 14 days ago to today
                closing_price_in_period = values[-day:]['closing_price'].astype(float)
                x_range = range(len(closing_price_in_period))
                # specific array for linear regression in numpy
                specific_array = np.array([x_range, np.ones(len(x_range))]).T
                # calculate the line slope
                slope, intercept = np.linalg.lstsq(specific_array, closing_price_in_period, rcond=-1)[0]
                slopes.append(slope)
                # the line slope is positive?
                if slope > 0:
                    passed += 1
                # plot the slope line with green dotted lines
                date_back_to = len(values) - day
                regression_range = range(date_back_to, date_back_to + day)
                plt.plot(regression_range, (slope * x_range + intercept), "g--")
                # save png as w640, h480
                out_path = str(Path(out_folder) / f"{symbol_code}.png")
                plt.savefig(out_path)
                # resize png as w250, h200
                Image.open(out_path).resize((250, 200), Image.LANCZOS).save(out_path)
            if attempts == passed:
                # e.g. 14 days ago to today
                closing_price = values[-max(days):]['closing_price'].reset_index(drop=True)
                price = calc_price(closing_price)
                passed_records.append(DailyUptrends(
                    symbol=m_symbol.get(code=symbol_code),
                    stocks_price_oldest=price['initial'],
                    stocks_price_latest=price['latest'],
                    stocks_price_delta=price['delta']
                ))
            logging.info(formatted_text(symbol_code, slopes, passed, price))
        DailyUptrends.objects.bulk_create(passed_records)
        log_writter.batch_is_done(len(symbol_codes))

        # TODO: パフォーマンスカイゼンして！原因はsymbolマスタにtickerかぶり（社名変更）があるため。バッチの新規Symbol取り込み部分もなおす
        # TODO: -400日が何月何日なのか表示
