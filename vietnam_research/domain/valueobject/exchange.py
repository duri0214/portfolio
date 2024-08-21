from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    """
    通貨コードと金額を含む、特定の通貨

    Attributes:
        code (str): 通貨コード
        amount (float): 金額
    """

    code: str
    amount: float
