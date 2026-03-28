import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from bs4 import Tag


class MarketDataRowError(Exception):
    """MarketDataRowの初期化に失敗した場合の例外"""

    def __init__(self, message: str, tag_tr: Tag):
        super().__init__(message)
        self.tag_tr = tag_tr

    def get_simplified_html(self) -> str:
        """HTMLの各tdの内容をカンマ区切りで簡潔に返す"""
        tds = self.tag_tr.find_all("td")
        td_texts = []
        for td in tds:
            # tdの中身をテキストのみ抽出し、改行や余分な空白を除去
            text = td.get_text(strip=True).replace("\n", " ").replace("\t", " ")
            # 連続する空白を1つにまとめる
            text = " ".join(text.split())
            td_texts.append(text)
        return ", ".join(td_texts)


@dataclass(frozen=True)
class RssEntryVO:
    """
    RSSの1件分のエントリを表す値オブジェクト。

    Attributes:
        title: 記事のタイトル。
        summary: 記事の要約または説明文。
        link: 記事のURL。
        updated: 記事の更新日時（文字列）。
    """

    title: str
    summary: str
    link: str
    updated: str | None

    @classmethod
    def from_feedparser_entry(cls, e):
        title = e.get("title", "")
        summary = e.get("summary", e.get("description", ""))
        link = e.get("link", "")
        updated = e.get("updated") or e.get("published")
        return cls(title=title, summary=summary, link=link, updated=updated)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "link": self.link,
            "updated": self.updated,
        }


@dataclass(frozen=True)
class NumericCellVO:
    """
    文字列の数値セルを表す値オブジェクト。

    数値変換の仕様:
    - カンマとパーセント記号を除去
    - 空文字は 0.0
    - "-" は None
    - 上記以外は float 変換

    Attributes:
        raw: パース対象の文字列（カンマ、%などを含む可能性がある）。
    """

    raw: str

    def to_float(self) -> float | None:
        s = (self.raw or "").replace(",", "").replace("%", "").strip()
        if s == "":
            return 0.0
        if s == "-":
            return None
        return float(s)


class Counting:
    """
    ウェブページのセルから数値を抽出・保持する値オブジェクト。

    Attributes:
        raw_value: 抽出元の生文字列。
        value: 数値に変換された値。
    """

    def __init__(self, raw_value: str):
        self.raw_value = raw_value
        self.value = NumericCellVO(raw_value).to_float()


@dataclass(frozen=True)
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
    """
    ベトナム株式の市場データ（1銘柄分）を表す値オブジェクト。

    Attributes:
        code: 証券コード。
        name: 銘柄名。
        industry_title: 業界情報のフルタイトル（例：[銀行] 商業銀行）。
        industry1: 業界大分類。
        industry2: 業界小分類。
        open_price: 始値。
        high_price: 高値。
        low_price: 安値。
        closing_price: 終値。
        volume: 出来高。
        marketcap: 時価総額（単位：10億ドン）。
        per: PER（株価収益率）。
    """

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

        # 業種情報の存在チェック
        if len(tag_tds_center) < 2:
            raise MarketDataRowError(
                "業種情報（table_list_centerが2つ未満）がありません", tr
            )

        # imgタグの存在チェック
        if not tag_tds_center[1].find("img"):
            raise MarketDataRowError("業種画像（imgタグ）がありません", tr)

        try:
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

            # 計数データの存在チェック
            if len(tag_tds_right) < 11:
                raise MarketDataRowError(
                    "計数データが不足しています（table_list_rightが11未満）", tr
                )

            self.open_price = tag_tds_right[2].value
            self.high_price = tag_tds_right[3].value
            self.low_price = tag_tds_right[4].value
            self.closing_price = tag_tds_right[1].value
            self.volume = tag_tds_right[7].value
            self.marketcap = tag_tds_right[9].value
            self.per = tag_tds_right[10].value

        except (AttributeError, IndexError, TypeError) as e:
            raise MarketDataRowError(f"データ解析でエラーが発生しました: {str(e)}", tr)


class IndustryGraphVO:
    """
    業界グラフの描画用データを保持し、計算ロジックを提供する値オブジェクト。

    Attributes:
        ticker: 銘柄コードまたは業界識別子。
        closing_price: 時系列の終値データ。
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
