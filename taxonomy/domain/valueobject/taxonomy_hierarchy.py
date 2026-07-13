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
