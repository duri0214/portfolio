import logging
import os
from abc import ABC, abstractmethod

import stripe

from shopping.domain.valueobject.payment import PaymentIntent, PaymentResult

# ロガーの取得
logger = logging.getLogger(__name__)


class PaymentServiceBase(ABC):
    """支払い処理のサービスの基底クラス"""

    @abstractmethod
    def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        """支払いを作成する"""
        pass

    @abstractmethod
    def confirm_payment(self, payment_id: str) -> PaymentResult:
        """支払いを確認する"""
        pass

    @abstractmethod
    def refund_payment(
        self, payment_id: str, amount: int | None = None
    ) -> PaymentResult:
        """支払いを返金する"""
        pass


class StripePaymentService(PaymentServiceBase):
    """Stripe APIを使った支払いサービスの実装"""

    def __init__(self):
        self.api_key = os.environ.get("STRIPE_API_KEY")
        stripe.api_key = self.api_key

    def create_payment(self, intent: PaymentIntent) -> PaymentResult:
        try:
            if intent.payment_method:
                charge = stripe.Charge.create(
                    amount=intent.amount,
                    currency=intent.currency,
                    description=intent.description,
                    source=intent.payment_method,  # トークンをsourceとして使用
                )
                logger.info(
                    f"支払い成功: ID={charge.id}, 金額={intent.amount}{intent.currency}"
                )
                return PaymentResult(
                    success=True,
                    payment_id=charge.id,
                )
            else:
                # 通常のPaymentIntentフロー（クライアントサイド決済用）
                payment_intent = stripe.PaymentIntent.create(
                    amount=intent.amount,
                    currency=intent.currency,
                    description=intent.description,
                )
                logger.info(
                    f"PaymentIntent作成成功: ID={payment_intent.id}, 金額={intent.amount}{intent.currency}"
                )
                return PaymentResult(
                    success=True,
                    payment_id=payment_intent.id,
                    client_secret=payment_intent.client_secret,
                )
        except stripe.error.CardError as e:
            error_message = f"カード決済エラー: {e.error.message}"
            logger.warning(error_message, extra={"error_code": e.error.code})
            return PaymentResult(
                success=False,
                error_message=error_message,
                error_code="card_error",
            )
        except stripe.error.RateLimitError as e:
            error_message = f"APIリクエスト制限エラー: {e.error.message}"
            logger.warning(error_message)
            return PaymentResult(
                success=False,
                error_message=error_message,
                error_code="rate_limit",
            )
        except stripe.error.AuthenticationError as e:
            error_message = f"API認証エラー: {e.error.message}"
            logger.error(error_message)
            return PaymentResult(
                success=False,
                error_message=error_message,
                error_code="auth_error",
            )
        except (stripe.error.APIConnectionError, stripe.error.APIError) as e:
            error_message = (
                f"API接続エラーまたはStripeサービスの問題: {e.error.message}"
            )
            logger.error(error_message)
            return PaymentResult(
                success=False,
                error_message=error_message,
                error_code="api_error",
            )
        except stripe.error.StripeError as e:
            error_message = f"その他のStripe関連エラー: {e.error.message}"
            logger.error(error_message)
            return PaymentResult(
                success=False,
                error_message=error_message,
                error_code="stripe_error",
            )
        except Exception as e:
            error_message = f"支払い処理中に予期しないエラー: {e}"
            logger.critical(error_message, exc_info=True)
            return PaymentResult(
                success=False,
                error_message="システムエラーが発生しました。",
                error_code="system_error",
            )

    def confirm_payment(self, payment_id: str) -> PaymentResult:
        pass

    def refund_payment(
        self, payment_id: str, amount: int | None = None
    ) -> PaymentResult:
        pass
