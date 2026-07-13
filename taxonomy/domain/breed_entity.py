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
        self.kingdom_id: int | None = record.get("kingdom_id")
        if self.kingdom_id is None:
            self.kingdom_id = record.get("kingdom_id_value")
        self.kingdom: str = record.get("kingdom_name")
        self.phylum_id: int | None = record.get("phylum_id")
        if self.phylum_id is None:
            self.phylum_id = record.get("phylum_id_value")
        self.phylum: str = record.get("phylum_name")
        self.classification_id: int | None = record.get("classification_id")
        if self.classification_id is None:
            self.classification_id = record.get("classification_id_value")
        self.classification: str = record.get("classification_name")
        self.family_id: int | None = record.get("family_id")
        if self.family_id is None:
            self.family_id = record.get("family_id_value")
        self.family: str = record.get("family_name")
        self.genus_id: int | None = record.get("genus_id")
        if self.genus_id is None:
            self.genus_id = record.get("genus_id_value")
        self.genus: str = record.get("genus_name")
        self.species_id: int | None = record.get("species_id")
        if self.species_id is None:
            self.species_id = record.get("species_id_value")
        self.species: str = record.get("species_name")
        self.breed_id: int | None = record.get("breed_id")
        if self.breed_id is None:
            self.breed_id = record.get("breed_id_value")
        self.breed: str = record.get("breed_name")
        self.breed_kana: str = record.get("breed_name_kana")
        self.natural_monument: str = record.get("natural_monument_name")
        self.breed_tag: str = record.get("breed_tag")

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

    def get_taxonomy_items(self) -> list[dict[str, int | str | None]]:
        """
        グラフ変換で使う分類階層を上位から順に返す。

        Returns:
            rank、id、name を持つ分類階層のリスト。
        """
        return [
            {"rank": "kingdom", "id": self.kingdom_id, "name": self.kingdom},
            {"rank": "phylum", "id": self.phylum_id, "name": self.phylum},
            {
                "rank": "classification",
                "id": self.classification_id,
                "name": self.classification,
            },
            {"rank": "family", "id": self.family_id, "name": self.family},
            {"rank": "genus", "id": self.genus_id, "name": self.genus},
            {"rank": "species", "id": self.species_id, "name": self.species},
            {"rank": "breed", "id": self.breed_id, "name": self.breed},
        ]
