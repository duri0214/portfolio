from taxonomy.domain.valueobject.taxonomy_hierarchy import TaxonomyHierarchyItem


class BreedEntity:
    """
    kingdom界 - phylum門 - classification綱 - family科 - genus属 - species腫 - breed品種

    Attributes:
        kingdom_id: 界のID。
        kingdom: 界名。
        phylum_id: 門のID。
        phylum: 門名。
        classification_id: 綱のID。
        classification: 綱名。
        family_id: 科のID。
        family: 科名。
        genus_id: 属のID。
        genus: 属名。
        species_id: 種のID。
        species: 種名。
        breed_id: 品種・系統・分類対象のID。
        breed: 品種・系統・分類対象名。
        breed_kana: 品種・系統・分類対象名のよみがな。
        natural_monument: 天然記念物区分。
        breed_tag: 品種タグ。
    """

    def __init__(self, record: dict):
        self.kingdom_id: int | None = self._get_record_value(record, "kingdom_id")
        self.kingdom: str = record.get("kingdom_name")
        self.phylum_id: int | None = self._get_record_value(record, "phylum_id")
        self.phylum: str = record.get("phylum_name")
        self.classification_id: int | None = self._get_record_value(
            record, "classification_id"
        )
        self.classification: str = record.get("classification_name")
        self.family_id: int | None = self._get_record_value(record, "family_id")
        self.family: str = record.get("family_name")
        self.genus_id: int | None = self._get_record_value(record, "genus_id")
        self.genus: str = record.get("genus_name")
        self.species_id: int | None = self._get_record_value(record, "species_id")
        self.species: str = record.get("species_name")
        self.breed_id: int | None = self._get_record_value(record, "breed_id")
        self.breed: str = record.get("breed_name")
        self.breed_kana: str = record.get("breed_name_kana")
        self.natural_monument: str = record.get("natural_monument_name")
        self.breed_tag: str = record.get("breed_tag")

    @staticmethod
    def _get_record_value(record: dict, key: str):
        for candidate_key in (key, key.replace("_id", "_source_id"), f"{key}_value"):
            value = record.get(candidate_key)
            if value is not None:
                return value
        return None

    def get_taxonomies(self) -> list:
        return [
            self.kingdom,
            self.phylum,
            self.classification,
            self.family,
            self.genus,
            self.species,
            self.breed,
        ]

    def get_taxonomy_items(self) -> list[TaxonomyHierarchyItem]:
        """
        グラフ変換で使う分類階層を上位から順に返す。

        Returns:
            分類階層1要素を表すValue Objectのリスト。
        """
        return [
            TaxonomyHierarchyItem("kingdom", self.kingdom_id, self.kingdom),
            TaxonomyHierarchyItem("phylum", self.phylum_id, self.phylum),
            TaxonomyHierarchyItem(
                "classification", self.classification_id, self.classification
            ),
            TaxonomyHierarchyItem("family", self.family_id, self.family),
            TaxonomyHierarchyItem("genus", self.genus_id, self.genus),
            TaxonomyHierarchyItem("species", self.species_id, self.species),
            TaxonomyHierarchyItem("breed", self.breed_id, self.breed),
        ]
