from abc import ABC, abstractmethod

from django.db import IntegrityError, DatabaseError

from shopping.models import Products, BuyingHistory


class PaymentRepositoryBase(ABC):
    """支払い処理のリポジトリの基底クラス"""

    @abstractmethod
    def save_payment_record(
        self, product_id: int, user_id: int, amount: int, payment_provider_id: str
    ) -> bool:
        """支払い記録を保存する"""
        pass

    @abstractmethod
    def get_product_by_id(self, product_id: int) -> Products | None:
        """商品IDから商品を取得する"""
        pass

    @abstractmethod
    def get_unpaid_orders(self, user_id: int) -> list:
        """未払いの注文を取得する"""
        pass


class StripePaymentRepository(PaymentRepositoryBase):
    """Stripe支払いに関連するリポジトリの実装"""

    def save_payment_record(
        self, product_id: int, user_id: int, amount: int, payment_provider_id: str
    ) -> bool:
        try:
            BuyingHistory.objects.create(
                product_id=product_id,
                user_id=user_id,
                amount=amount,
                stripe_id=payment_provider_id,
                payment_status=BuyingHistory.COMPLETED,
            )
            return True
        except IntegrityError as e:
            print(f"支払い記録の整合性エラー: {e}")
            return False
        except DatabaseError as e:
            print(f"データベースエラー: {e}")
            return False
        except Exception as e:
            print(f"予期しない例外が発生: {e}")
            raise  # 上位に再スロー

    def get_product_by_id(self, product_id: int) -> Products | None:
        try:
            return Products.objects.get(id=product_id)
        except Products.DoesNotExist:
            return None

    def get_unpaid_orders(self, user_id: int) -> list:
        return list(
            BuyingHistory.objects.filter(
                user_id=user_id, payment_status=BuyingHistory.PENDING
            )
        )
