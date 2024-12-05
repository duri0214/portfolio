import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
from bs4 import Tag


@dataclass
class Counting:
    """
    計数を表すクラスです

    属性:
        raw_value (str): 整形前の数値
        value (float | None): 整形後の数値。

    注意点: tds[7] は前日比で 1.1% のように `%` が混ざり込んでいる。数値として扱うために、("%", "")に置換を行います。

    また `raw_value` が ""（空文字）の場合、`value` は 0.0 とします。
    `raw_value` が "-" の場合、`value` は None とします。
    それ以外の場合は、`raw_value`をfloat型に変換して`value`に設定します。

    Notes: tds[7] は前日比で 1.1% のように `%` が混ざり込んでいる。あくまで数字として扱うので置換をかける
    """

    raw_value: str
    value: float | None = field(init=False)

    def __init__(self, raw_value: str):
        self.raw_value = raw_value.replace(",", "").replace("%", "")
        if self.raw_value == "":
            self.value = 0.0
        elif self.raw_value == "-":
            self.value = None
        else:
            self.value = float(self.raw_value)


@dataclass
class TransactionDate:
    """
    ウェブページから日付情報を抽出し、標準のdatetime形式に変換する。

    Attributes:
        th_tag: BeautifulSoupで抽出したHTMLのthタグ。
    """

    th_tag: Tag

    def to_date(self) -> datetime:
        """
        BeautifulSoupで抽出したHTMLのthタグから文字列形式の日付('YYYY/MM/DD HH:MM')
        を抽出し、それをdatetimeオブジェクトに変換する。

        Returns:
            対応するdatetimeオブジェクト。

        Raises:
            ValueError: thタグから抽出した日付文字列が 'YYYY/MM/DD HH:MM' 形式でない場合に発生。
        """
        raw_text = self.th_tag.find("b").text.strip()
        extracted = re.search(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}", raw_text)
        if not extracted:
            raise ValueError("`YYYY/MM/DD HH:MM`形式が入力されていない")

        date_str = f"{extracted.group()}:00"
        return datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")


@dataclass
class MarketDataRow:
    code: str
    name: str
    industry1: str
    industry2: str
    open_price: float
    high_price: float
    low_price: float
    closing_price: float
    volume: float
    marketcap: float
    per: float

    def __init__(self, tr: Tag):
        super().__init__()
        tag_tds_center = tr.find_all("td", class_="table_list_center")
        self.code = re.sub("＊", "", tag_tds_center[0].text.strip())
        self.name = tag_tds_center[0].a.get("title")
        self.industry_title = tag_tds_center[1].img.get("title")
        self.industry1 = re.sub(r"\[(.+)]", "", self.industry_title)
        self.industry2 = re.search(
            r"(?<=\[).*?(?=])", tag_tds_center[1].img.get("title")
        ).group()

        tag_tds_right = [
            Counting(td.text.strip())
            for td in tr.find_all("td", class_="table_list_right")
        ]
        self.open_price = tag_tds_right[2].value
        self.high_price = tag_tds_right[3].value
        self.low_price = tag_tds_right[4].value
        self.closing_price = tag_tds_right[1].value
        self.volume = tag_tds_right[7].value
        self.marketcap = tag_tds_right[9].value
        self.per = tag_tds_right[10].value


class IndustryGraphVO:
    """
    業界のグラフの生成に関連したデータとメソッドを保持するクラス
    """

    def __init__(self, ticker: str, closing_price: pd.Series):
        """
        IndustryGraphVOオブジェクトを初期化する。

        Args:
            ticker (str): 株のティッカーシンボル
            closing_price (pd.Series): 終値のデータ
        """
        self.ticker = ticker
        self.closing_price = closing_price

    def plot_values(self) -> tuple[range, pd.Series]:
        """
        描画するための値を返す。

        Returns:
            tuple[Range, pd.Series]: 描画のためのx軸の範囲と終値のデータ。
        """
        x_range = range(len(self.closing_price))
        return x_range, self.closing_price

    def plot_sma(self, periods: list[int]) -> Iterable[pd.Series]:
        """
        指定された期間の平均値を描画する。

        Args:
            periods (list[int]): 平均を計算する期間のリスト。

        Yields:
            pd.Series: ローリング平均のシリーズ。
        """
        for period in periods:
            yield self.closing_price.rolling(period).mean()

    def plot_regression_slope(self, day: int):
        """
        指定された日数の回帰直線の勾配（傾斜）を描画する。

        Args:
            day (int): 回帰直線を計算する日数。

        Yields:
            tuple[float, range, np.ndarray]: 勾配、回帰直線の範囲、回帰直線の値のリスト
        """
        closing_price_in_period = self.closing_price[-day:].astype(float)
        x_range = range(len(closing_price_in_period))
        specific_array = np.array([x_range, np.ones(len(x_range))]).T
        slope, intercept = np.linalg.lstsq(
            specific_array, closing_price_in_period, rcond=-1
        )[0]
        date_back_to = len(self.closing_price) - day
        regression_range = range(date_back_to, date_back_to + day)
        return slope, regression_range, (slope * x_range + intercept)
