from django.db import models
from django.db.models import Count, QuerySet
from django.db.models.functions import Concat

from rental_shop.models import Item


def get_item_position_counts(warehouse_id: int) -> QuerySet:
    """
    倉庫内の各位置にあるアイテムの数を取得します。
    各位置のアイテムの名前とレンタル状況も連結します。
    """
    return (
        Item.objects.filter(warehouse_id=warehouse_id, rental_status_id=1)
        .values("pos_y", "pos_x")
        .annotate(
            num_items=Count("id"),
            items=Concat(
                "name", "rental_status", output_field=models.TextField(), separator=","
            ),
        )
        .order_by("pos_y", "pos_x")
    )
