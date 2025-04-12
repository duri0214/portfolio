from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentIntent:
    """支払い意図を表す値オブジェクト"""

    amount: int
    currency: str
    description: str | None = None
    payment_method: str | None = None


@dataclass(frozen=True)
class PaymentResult:
    """支払い結果を表す値オブジェクト"""

    success: bool
    payment_id: str | None = None
    error_message: str | None = None
    client_secret: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class PaymentInfo:
    """支払い情報を表す値オブジェクト"""

    product_id: int
    user_id: int
    quantity: int
    price: float
    subtotal: float
    tax_amount: float
    total_amount: float
    tax_rate: float

    def to_dict(self) -> dict:
        """セッション保存用の辞書形式に変換"""
        return {
            "product_id": self.product_id,
            "user_id": self.user_id,
            "quantity": self.quantity,
            "price": self.price,
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "tax_rate": self.tax_rate,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaymentInfo":
        """辞書形式からPaymentInfoオブジェクトを生成"""
        return cls(
            product_id=data["product_id"],
            user_id=data["user_id"],
            quantity=data["quantity"],
            price=data["price"],
            subtotal=data["subtotal"],
            tax_amount=data["tax_amount"],
            total_amount=data["total_amount"],
            tax_rate=data["tax_rate"],
        )

    # フォーマット済みのプロパティを追加
    @property
    def formatted_price(self) -> str:
        """単価（カンマ区切り）"""
        return f"{self.price:,.0f}"

    @property
    def formatted_subtotal(self) -> str:
        """小計（カンマ区切り）"""
        return f"{self.subtotal:,.0f}"

    @property
    def formatted_tax_amount(self) -> str:
        """税額（カンマ区切り）"""
        return f"{self.tax_amount:,.0f}"

    @property
    def formatted_total_amount(self) -> str:
        """合計額（カンマ区切り）"""
        return f"{self.total_amount:,.0f}"
