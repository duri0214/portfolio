from django.db import models
from django.db.models import Count, QuerySet
from django.db.models.functions import Concat

from rental_shop.domain.valueobject.warehouse import (
    Warehouse as WarehouseVO,
    Shelf,
    ShelfRow,
    ShelfCell,
)
from rental_shop.models import Item, RentalStatus, UserAttribute


class WarehouseRepository:
    """
    倉庫情報を取得するためのリポジトリ。

    各倉庫に配置されているアイテムの状況や在庫、カート内のアイテム情報を集約して
    Warehouse VO（Value Object）のリストを構築します。
    """

    @staticmethod
    def get_item_position_counts(warehouse_id: int) -> QuerySet:
        """
        倉庫内の棚の各位置（x, y座標）に存在する「在庫あり」アイテムの数を集計します。

        この集計結果は、倉庫の棚を可視化（マトリックス表示）するために使用されます。

        Args:
            warehouse_id (int): 集計対象の倉庫ID。

        Returns:
            QuerySet: 各位置（pos_y, pos_x）ごとのアイテム数（num_items）と、
                     アイテム名などの連結情報（items）を含むクエリセット。
        """
        # 在庫ありのアイテムのみを対象とする（棚に並んでいる状態のもの）
        return (
            Item.objects.filter(
                warehouse_id=warehouse_id, rental_status_id=RentalStatus.STOCK
            )
            .values("pos_y", "pos_x")
            .annotate(
                num_items=Count("id"),
                items=Concat(
                    "name",
                    "rental_status",
                    output_field=models.TextField(),
                    separator=",",
                ),
            )
            .order_by("pos_y", "pos_x")
        )

    @classmethod
    def find_by_staff(cls, staff: UserAttribute) -> list[WarehouseVO]:
        """
        指定されたスタッフが所属するすべての倉庫の情報を構築し、Warehouse VO のリストを返します。

        各倉庫について、以下の情報を収集します：
        1. 棚の配置情報（ShelfRow, ShelfCell のマトリックス）
        2. 在庫ありのアイテム（STOCK）
        3. 貸出中（RENTAL かつ 請求書発行済み）のアイテム
        4. 現在カートに入っているアイテム（CART）

        Args:
            staff (UserAttribute): スタッフのモデルインスタンス。

        Returns:
            list[WarehouseVO]: 各倉庫の詳細情報を含む Warehouse 値オブジェクトのリスト。
        """
        warehouse_list = staff.warehouses.all()

        warehouse_vos = []
        for warehouse in warehouse_list:
            # 棚のマトリックス（ShelfVO）を構築
            item_position_counts = cls.get_item_position_counts(warehouse.id)
            shelves = [cls._create_shelf(warehouse, item_position_counts)]

            # ステータスごとのアイテムを取得
            available_items = Item.objects.filter(
                warehouse_id=warehouse.id, rental_status_id=RentalStatus.STOCK
            )
            non_available_items = Item.objects.filter(
                warehouse_id=warehouse.id,
                rental_status_id=RentalStatus.RENTAL,
                invoice__isnull=False,
            )
            cart_items = Item.objects.filter(
                warehouse_id=warehouse.id, rental_status_id=RentalStatus.CART
            )

            # Warehouse VO にまとめてリストに追加
            warehouse_vos.append(
                WarehouseVO(
                    instance=warehouse,
                    shelves=shelves,
                    available_items=available_items,
                    non_available_items=non_available_items,
                    cart_items=cart_items,
                )
            )

        return warehouse_vos

    @staticmethod
    def _create_shelf(warehouse, item_position_counts: QuerySet) -> Shelf:
        """
        倉庫の高さ・幅に基づき、各座標のアイテム数を埋めた Shelf VO を作成します。

        Args:
            warehouse: 倉庫のモデルインスタンス（height, width 属性を使用）。
            item_position_counts (QuerySet): get_item_position_counts() で取得した集計結果。

        Returns:
            Shelf: 棚の行とセルの階層構造を持つ Shelf 値オブジェクト。
        """
        # 1. 初期状態の棚を作成（全ての座標にアイテム数 0 のセルを配置）
        shelf_rows = []
        for _ in range(warehouse.height):
            # 各行に、倉庫の幅（width）分のセル（ShelfCell）を生成
            shelf_row = ShelfRow(
                cells=[ShelfCell(item_count=0) for _ in range(warehouse.width)]
            )
            shelf_rows.append(shelf_row)

        # 2. 集計データ（DB上の各座標の個数）を棚のセルにマッピング
        # DB上の座標 (pos_x, pos_y) は 1 から始まる（1-based）ため、
        # 配列のインデックス（0-based）に合わせて -1 して代入する。
        for row_data in item_position_counts:
            y_idx = row_data["pos_y"] - 1
            x_idx = row_data["pos_x"] - 1
            shelf_rows[y_idx].cells[x_idx].item_count += row_data["num_items"]

        return Shelf(rows=shelf_rows)
