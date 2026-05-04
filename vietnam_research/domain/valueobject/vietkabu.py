import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from bs4 import Tag

MARKET_DATA_EXPECTED_COLUMNS = (
    "銘柄",
    "前日 終値",
    "取引値 (終値)",
    "始値",
    "高値",
    "安値",
    "前日比",
    "前日比 (%)",
    "売買高 (株)",
    "時価総額 (百万ドン)",
    "時価総額 (億円)",
    "PER (倍)",
    "外国人 [買]成立",
    "外国人 [売]成立",
    "業種",
)


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


class MarketDataHeaderError(Exception):
    """
    viet-kabuの株価テーブルヘッダーが期待と異なる場合の例外。

    ヘッダー不一致だけを呼び出し側で明示的にハンドリングするための専用例外。
    `ValueError` などの汎用例外にすると、想定外の不具合まで同じ扱いで
    握ってしまうリスクがあるため分離している。
    """


@dataclass(frozen=True)
class MarketDataTableHeader:
    """
    viet-kabuの株価テーブルヘッダー定義を表す値オブジェクト。

    `validate_from_soup` は以下を実行する:
    - `th` から株価テーブルのヘッダー行を検出する
    - ヘッダー文字列を正規化する（空白揺れ・全角括弧の揺れを吸収）
    - 期待ヘッダー（列名 + 順序）と完全一致することを検証する

    検証に成功した場合、列名からセル位置を引ける `column_indexes` を保持して返す。
    検証に失敗した場合は `MarketDataHeaderError` を送出する。

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """

    column_indexes: dict[str, int]

    @classmethod
    def validate_from_soup(cls, soup) -> "MarketDataTableHeader":
        """
        soupからtrを抽出した集まりの中で、`th` を持つ行を走査し、
        株価テーブルのヘッダー行を検出して期待ヘッダーと照合する。

        処理の流れ:
        1. `th` を持つ行を走査し、`_looks_like_market_data_header` で候補行を絞る
        2. 候補行のヘッダー文字列を正規化する
        3. `MARKET_DATA_EXPECTED_COLUMNS`（列名 + 順序）との完全一致を検証する

        Returns:
            検証済みヘッダーの `column_indexes` を保持した `MarketDataTableHeader`。

        Raises:
            MarketDataHeaderError:
                株価テーブルのヘッダー行が見つからない、または期待ヘッダーと不一致の場合。
        """
        expected_columns = tuple(
            cls._normalize_text(c) for c in MARKET_DATA_EXPECTED_COLUMNS
        )

        for tr in soup.find_all("tr"):
            th_tags = tr.find_all("th")
            if not th_tags:
                continue

            columns = tuple(
                cls._normalize_text(th.get_text(" ", strip=True)) for th in th_tags
            )
            if not cls._looks_like_market_data_header(columns):
                continue

            if columns != expected_columns:
                raise MarketDataHeaderError(
                    "viet-kabuの株価テーブルヘッダーが期待と異なります。"
                    f" expected={expected_columns}, actual={columns}"
                )

            return cls({column: i for i, column in enumerate(columns)})

        raise MarketDataHeaderError(
            "viet-kabuの株価テーブルヘッダーが見つかりません。"
            f" expected={expected_columns}"
        )

    @classmethod
    def _looks_like_market_data_header(cls, columns: tuple[str, ...]) -> bool:
        """
        与えられたヘッダー列が「株価データ本体のヘッダー行らしいか」を判定する。

        この判定は完全一致チェックの前段で使う粗いフィルタで、ページ内の他テーブルや
        装飾用ヘッダー行を除外する目的を持つ。
        現在は株価テーブルに必須の `銘柄` と `業種` が同時に含まれることを条件にしている。
        """
        return "銘柄" in columns and "業種" in columns

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        text = value.replace("\xa0", " ")
        text = text.replace("（", "(").replace("）", ")")
        return " ".join(text.split())

    def index(self, column: str) -> int:
        normalized_column = self._normalize_text(column)
        return self.column_indexes[normalized_column]


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

    def __init__(self, tr: Tag, table_header: MarketDataTableHeader):
        super().__init__()
        tag_tds = [
            td
            for td in tr.find_all("td")
            if "table_list_center" in td.get_attribute_list("class")
            or "table_list_right" in td.get_attribute_list("class")
        ]

        # 業種情報の存在チェック
        if len(tag_tds) != len(MARKET_DATA_EXPECTED_COLUMNS):
            raise MarketDataRowError(
                "データ列数がヘッダー列数と一致しません"
                f"（expected={len(MARKET_DATA_EXPECTED_COLUMNS)}, actual={len(tag_tds)}）",
                tr,
            )

        ticker_cell = tag_tds[table_header.index("銘柄")]
        industry_cell = tag_tds[table_header.index("業種")]

        # imgタグの存在チェック
        if not industry_cell.find("img"):
            raise MarketDataRowError("業種画像（imgタグ）がありません", tr)

        try:
            self.code = re.sub("＊", "", ticker_cell.text.strip())
            self.name = ticker_cell.a.get("title")
            self.industry_title = industry_cell.img.get("title")
            self.industry1 = re.sub(r"\[(.+)]", "", self.industry_title)
            self.industry2 = re.search(
                r"(?<=\[).*?(?=])", industry_cell.img.get("title")
            ).group()

            self.open_price = self._counting_value(tag_tds, table_header, "始値")
            self.high_price = self._counting_value(tag_tds, table_header, "高値")
            self.low_price = self._counting_value(tag_tds, table_header, "安値")
            self.closing_price = self._counting_value(
                tag_tds, table_header, "取引値 (終値)"
            )
            self.volume = self._counting_value(tag_tds, table_header, "売買高 (株)")
            self.marketcap = self._counting_value(
                tag_tds, table_header, "時価総額 (億円)"
            )
            self.per = self._counting_value(tag_tds, table_header, "PER (倍)")

        except (AttributeError, IndexError, TypeError) as e:
            raise MarketDataRowError(f"データ解析でエラーが発生しました: {str(e)}", tr)

    @classmethod
    def _counting_value(
        cls, tag_tds: list[Tag], table_header: MarketDataTableHeader, column: str
    ) -> float | None:
        return Counting(tag_tds[table_header.index(column)].text.strip()).value


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
