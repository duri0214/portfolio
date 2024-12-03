import re
from dataclasses import dataclass, field
from datetime import datetime

from bs4 import Tag


@dataclass
class Company:
    code: str
    name: str = None
    industry1: str = None
    industry2: str = None


@dataclass
class Counting:
    """
    計数を表すクラスです

    Attributes:
        raw_value (str): constructor
        value (float): The value of the number.

    Notes: tds[7] は前日比で 1.1% のように `%` が混ざり込んでいる。あくまで数字として扱うので置換をかける
    """

    raw_value: str
    value: float = field(init=False)

    def __init__(self, raw_value: str):
        self.raw_value = raw_value.replace(",", "").replace("%", "")
        if self.raw_value == "":
            self.value = 0.0
        elif self.raw_value == "-":
            raise ValueError("Invalid value: '-'")
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
        company = Company(
            code=re.sub("＊", "", tag_tds_center[0].text.strip()),
            name=tag_tds_center[0].a.get("title"),
            industry1=re.sub(r"\[(.+)]", "", tag_tds_center[1].img.get("title")),
            industry2=re.search(
                r"(?<=\[).*?(?=])", tag_tds_center[1].img.get("title")
            ).group(),
        )
        self.code = company.code
        self.name = company.name
        self.industry1 = company.industry1
        self.industry2 = company.industry2

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
