from abc import ABC, abstractmethod

from django.db import IntegrityError, DatabaseError

from shopping.models import BuyingHistory, Product


class PaymentRepositoryBase(ABC):
    """支払い処理のリポジトリの基底クラス"""

    @abstractmethod
    def save_payment_record(
        self, product_id: int, user_id: int, amount: int, payment_provider_id: str
    ) -> bool:
        """支払い記録を保存する"""
        pass

    @abstractmethod
    def get_unpaid_orders(self, user_id: int) -> list:
        """未払いの注文を取得する"""
        pass

    @abstractmethod
    def calculate_payment_amounts(
        self, product_id: int, quantity: int, tax_rate: float | None = None
    ) -> dict:
        """支払い金額の内訳を計算する"""
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

    def get_unpaid_orders(self, user_id: int) -> list:
        return list(
            BuyingHistory.objects.filter(
                user_id=user_id, payment_status=BuyingHistory.PENDING
            )
        )

    def calculate_payment_amounts(
        self, product_id: int, quantity: int, tax_rate: float | None = None
    ) -> dict:
        """
        商品IDと数量から支払い金額の内訳を計算する

        Args:
            product_id: 商品ID
            quantity: 購入数量
            tax_rate: 税率（指定がない場合はデフォルト値の0.10が使用される）

        Returns:
            金額内訳の辞書 (subtotal, tax_amount, total_amount)
        """
        try:
            product = Product.objects.get(id=product_id)
            price = product.price

            # 税率のデフォルト値
            if tax_rate is None:
                tax_rate = 0.10

            subtotal = price * quantity
            tax_amount = int(subtotal * tax_rate)
            total_amount = subtotal + tax_amount

            return {
                "price": price,
                "quantity": quantity,
                "subtotal": subtotal,
                "tax_amount": tax_amount,
                "total_amount": total_amount,
                "tax_rate": tax_rate,
            }
        except Product.DoesNotExist:
            raise ValueError(f"商品ID {product_id} が見つかりません")
        except Exception as e:
            print(f"金額計算中にエラーが発生しました: {e}")
            raise
