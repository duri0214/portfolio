from dataclasses import dataclass

from django.db.models import QuerySet

from warehouse.models import Warehouse


@dataclass
class ShelfCell:
    """
    倉庫の棚の一つのセルを表現する値オブジェクト。

    属性:
        item_count: このセルに存在するアイテムの数量。
    """

    item_count: int


@dataclass
class ShelfRow:
    """
    倉庫の棚の一つの行を表現する値オブジェクト。

    属性:
        cells: この行に存在するセルのリスト。
    """

    cells: list[ShelfCell]


@dataclass
class Shelf:
    """
    倉庫の棚を表現する値オブジェクト。

    属性:
        rows: この棚に存在する行のリスト。
    """

    rows: list[ShelfRow]


@dataclass
class Warehouse:
    """
    倉庫を表現するデータクラス。

    属性:
        warehouse: 倉庫モデルのインスタンス。
        shelves: この倉庫に含まれる棚のリスト。各棚は`Shelf`インスタンスで表される。
        available_items: この倉庫に現在在庫があるアイテムのクエリセット。
        non_available_items: この倉庫に現在在庫がないアイテムのクエリセット。
    """

    warehouse: Warehouse
    shelves: list[Shelf]
    available_items: QuerySet
    non_available_items: QuerySet
