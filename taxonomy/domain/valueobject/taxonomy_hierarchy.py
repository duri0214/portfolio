from dataclasses import dataclass


TAXONOMY_HIERARCHY_RANKS = (
    "kingdom",
    "phylum",
    "classification",
    "family",
    "genus",
    "species",
    "breed",
)


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

    @classmethod
    def from_record(cls, rank: str, record: dict) -> "TaxonomyHierarchyItem":
        """
        Repository由来の平坦なdictから分類階層1要素を生成する。

        Args:
            rank: kingdom、phylum、breed などの階層種別。
            record: Repositoryやテストデータが渡す分類階層dict。

        Returns:
            id/name を1つにまとめた TaxonomyHierarchyItem。
        """
        source_id = cls._get_record_value(record, f"{rank}_id")
        return cls(
            rank=rank,
            source_id=source_id,
            name=record.get(f"{rank}_name") or "",
        )

    @staticmethod
    def _get_record_value(record: dict, key: str):
        for candidate_key in (key, key.replace("_id", "_source_id"), f"{key}_value"):
            value = record.get(candidate_key)
            if value is not None:
                return value
        return None

    @property
    def has_name(self) -> bool:
        return bool(self.name)


@dataclass(frozen=True)
class TaxonomyHierarchy:
    """
    界から品種までの分類階層全体を表すValue Object。

    Attributes:
        items: 固定順で並ぶ分類階層要素。
    """

    items: tuple[TaxonomyHierarchyItem, ...]

    @classmethod
    def from_record(cls, record: dict) -> "TaxonomyHierarchy":
        """
        Repository由来の平坦なdictから分類階層全体を生成する。

        Args:
            record: Repositoryが返す分類階層dict。

        Returns:
            固定順の分類階層。
        """
        return cls.from_items(
            [
                TaxonomyHierarchyItem.from_record(rank, record)
                for rank in TAXONOMY_HIERARCHY_RANKS
            ]
        )

    @classmethod
    def from_items(
        cls, items: list[TaxonomyHierarchyItem] | tuple[TaxonomyHierarchyItem, ...]
    ) -> "TaxonomyHierarchy":
        """
        分類階層要素から階層全体を生成する。

        Args:
            items: 界から品種までの分類階層要素。

        Returns:
            rankの欠損、重複、順序違いを検証済みの分類階層。
        """
        ordered_items = tuple(items)
        ranks = tuple(item.rank for item in ordered_items)
        if ranks != TAXONOMY_HIERARCHY_RANKS:
            expected = " -> ".join(TAXONOMY_HIERARCHY_RANKS)
            actual = " -> ".join(ranks)
            raise ValueError(
                f"分類階層の順序が不正です: expected={expected}, actual={actual}"
            )
        return cls(ordered_items)

    def names(self) -> list[str]:
        return [item.name for item in self.items]

    def get_item(self, rank: str) -> TaxonomyHierarchyItem:
        for item in self.items:
            if item.rank == rank:
                return item
        return TaxonomyHierarchyItem(rank, None, "")
