import os
from abc import ABC, abstractmethod

import stripe

from shopping.domain.valueobject.payment import PaymentIntent, PaymentResult


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
            payment_intent = stripe.PaymentIntent.create(
                amount=intent.amount,
                currency=intent.currency,
                description=intent.description,
            )
            return PaymentResult(
                success=True,
                payment_id=payment_intent.id,
                client_secret=payment_intent.client_secret,
            )
        except stripe.error.CardError as e:
            return PaymentResult(
                success=False,
                error_message=f"カード決済エラー: {e.error.message}",
                error_code="card_error",
            )
        except stripe.error.RateLimitError as e:
            return PaymentResult(
                success=False,
                error_message=f"APIリクエスト制限エラー: {e.error.message}",
                error_code="rate_limit",
            )
        except stripe.error.AuthenticationError as e:
            return PaymentResult(
                success=False,
                error_message=f"API認証エラー: {e.error.message}",
                error_code="auth_error",
            )
        except (stripe.error.APIConnectionError, stripe.error.APIError) as e:
            return PaymentResult(
                success=False,
                error_message=f"API接続エラーまたはStripeサービスの問題: {e.error.message}",
                error_code="api_error",
            )
        except stripe.error.StripeError as e:
            return PaymentResult(
                success=False,
                error_message=f"その他のStripe関連エラー: {e.error.message}",
                error_code="stripe_error",
            )
        except Exception as e:
            # TODO: printはloggerに置き換える（settings.pyに設定書いてあるから）
            print(f"支払い処理中に予期しないエラー: {e}")
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
