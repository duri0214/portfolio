class BreedEntity:
    """
    kingdom界 - phylum門 - classification綱 - family科 - genus属 - species腫 - breed品種
    """
    def __init__(self, record: dict):
        self.kingdom: str = record.get('kingdom_name')
        self.phylum: str = record.get('phylum_name')
        self.classification: str = record.get('classification_name')
        self.family: str = record.get('family_name')
        self.genus: str = record.get('genus_name')
        self.species: str = record.get('species_name')
        self.breed: str = record.get('breed_name')
        self.breed_kana: str = record.get('breed_name_kana')
        self.natural_monument: str = record.get('breed_name_kana')
        self.breed_tag: str = record.get('breed_tag')

    def get_taxonomies(self) -> list:
        return [self.kingdom, self.phylum, self.classification, self.family, self.genus, self.species, self.breed]
