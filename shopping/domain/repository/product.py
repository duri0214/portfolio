from shopping.models import Product


class ProductRepository:
    """製品関連のリポジトリ"""

    @staticmethod
    def get_all_products() -> list:
        """すべての製品を取得する"""
        return list(Product.objects.all().order_by("id"))

    @staticmethod
    def get_product_by_id(product_id: int) -> Product | None:
        """製品IDから製品を取得する"""
        try:
            return Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return None

    @staticmethod
    def save_product(product: Product) -> Product:
        """製品を保存する"""
        product.save()
        return product
