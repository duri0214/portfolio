from taxonomy.domain.valueobject.taxonomy_hierarchy import (
    TaxonomyHierarchy,
    TaxonomyHierarchyItem,
)


class BreedEntity:
    """
    kingdom界 - phylum門 - classification綱 - family科 - genus属 - species腫 - breed品種

    Attributes:
        hierarchy: 界から品種までの分類階層。
        breed_kana: 品種・系統・分類対象名のよみがな。
        natural_monument: 天然記念物区分。
        breed_tag: 品種タグ。
    """

    def __init__(self, record: dict):
        self.hierarchy = TaxonomyHierarchy.from_record(record)
        self.breed_kana: str = record.get("breed_name_kana")
        self.natural_monument: str = record.get("natural_monument_name")
        self.breed_tag: str = record.get("breed_tag")

    @classmethod
    def from_hierarchy_items(
        cls,
        hierarchy_items: list[TaxonomyHierarchyItem],
        breed_kana: str = "",
        natural_monument: str | None = None,
        breed_tag: str | None = None,
    ) -> "BreedEntity":
        """
        分類階層VOからBreedEntityを生成する。

        Args:
            hierarchy_items: 界から品種までの分類階層。
            breed_kana: 品種・系統・分類対象名のよみがな。
            natural_monument: 天然記念物区分。
            breed_tag: 品種タグ。

        Returns:
            分類階層を保持する BreedEntity。
        """
        entity = cls.__new__(cls)
        entity.hierarchy = TaxonomyHierarchy.from_items(hierarchy_items)
        entity.breed_kana = breed_kana
        entity.natural_monument = natural_monument
        entity.breed_tag = breed_tag
        return entity

    @property
    def breed_id(self) -> int | str | None:
        return self.hierarchy.get_item("breed").source_id

    @property
    def breed(self) -> str:
        return self.hierarchy.get_item("breed").name

    def get_taxonomies(self) -> list:
        return self.hierarchy.names()

    def get_taxonomy_items(self) -> list[TaxonomyHierarchyItem]:
        """
        グラフ変換で使う分類階層を上位から順に返す。

        Returns:
            分類階層1要素を表すValue Objectのリスト。
        """
        return list(self.hierarchy.items)
