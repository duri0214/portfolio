from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyHierarchyItem:
    """
    分類階層の1要素を表すValue Object。

    Attributes:
        rank: kingdom、phylum、breed などの階層種別。
        source_id: DB上の分類階層ID。未保存データではNone。
        name: 分類階層の表示名。
    """

    rank: str
    source_id: int | str | None
    name: str

    @property
    def has_name(self) -> bool:
        return bool(self.name)
