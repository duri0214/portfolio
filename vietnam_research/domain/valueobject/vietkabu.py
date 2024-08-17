from dataclasses import dataclass, field, InitVar


@dataclass
class Company:
    code: str
    name: str = None
    industry1: str = None
    industry2: str = None


@dataclass(frozen=True)
class Counting:
    """
    TdNumber は、tdテキストの数値を表すクラスです
     Attributes:
         _raw_text (str): 数値の初期化に使用される生のテキスト
         value (float): The value of the number.

     Methods:
         __post_init__(_raw_text: str): 生のテキストを float 値に変換します
         _to_float(s: str) -> float: 指定された文字列を浮動小数点数に変換します
    """

    _raw_text: InitVar[str]
    value: float = field(init=False)

    def __post_init__(self, _raw_text: str):
        if _raw_text == "-":
            raise ValueError("Invalid value: '-'")
        self.__dict__["value"] = self._to_float(_raw_text)

    @staticmethod
    def _to_float(s: str) -> float:
        """
        このメソッドは文字列を入力として受け取り、floatに変換して返します
        文字列が空の場合は 0.0 を返します。
        文字列内のカンマを置き換え、float() 関数を使用します

        Args:
            s (str): The string to be converted to float.

        Returns:
            float: The float value of the string.

        Raises:
            ValueError: 変換できない場合は、ValueError が発生します

        Notes: tds[7] は前日比で 1.1% のように `%` が混ざり込んでいる。あくまで数字として扱うので置換をかける
        """
        if s == "":
            return 0.0

        return float(s.replace(",", "").replace("%", ""))
