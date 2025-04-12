from shopping.models import Product


class ProductRepository:
    """製品関連のリポジトリ"""

    @staticmethod
    def get_all_products() -> list:
        """すべての製品を取得する"""
        return list(Product.objects.all().order_by("id"))
