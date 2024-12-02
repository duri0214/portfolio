import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import Tag


@dataclass
class TransactionDate:
    """
    ウェブページから日付情報を抽出し、標準のdatetime形式に変換します。

    Attributes:
        th_tag: BeautifulSoupで抽出されたHTMLのthタグ。
        transaction_date: thタグから抽出され、変換された日付情報を持つdatetimeオブジェクト。
    """

    th_tag: Tag
    transaction_date: datetime = None

    def __post_init__(self):
        tag_b = self.th_tag.find("b")
        self.transaction_date = self.convert_to_datetime(tag_b.text.strip())

    @staticmethod
    def convert_to_datetime(target_text: str) -> datetime:
        """
        文字列形式の日付('YYYY/MM/DD HH:MM')をdatetimeオブジェクトに変換します。

        Args:
            target_text: 文字列形式の日付。

        Returns:
            対応するdatetimeオブジェクト。

        Raises:
            ValueError: target_textが'YYYY/MM/DD HH:MM'形式でない場合に発生します。
        """
        extracted = re.search(r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}", target_text)
        if not extracted:
            raise ValueError("`YYYY/MM/DD HH:MM`形式が入力されませんでした")

        date_str = f"{extracted.group()}:00"
        return datetime.strptime(date_str, "%Y/%m/%d %H:%M:%S")
