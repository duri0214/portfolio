from dataclasses import dataclass
from enum import Enum


class PaymentStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class PaymentIntent:
    """支払い意図を表す値オブジェクト"""

    amount: int
    currency: str
    description: str | None = None


@dataclass(frozen=True)
class PaymentResult:
    """支払い結果を表す値オブジェクト"""

    success: bool
    payment_id: str | None = None
    error_message: str | None = None
    client_secret: str | None = None
    error_code: str | None = None
