class BreedEntity:
    """
    kingdom界 - phylum門 - classification綱 - family科 - genus属 - species腫 - breed品種
    """
    def __init__(self, record: dict):
        self.kingdom = record.get('kingdom_name')
        self.phylum = record.get('phylum_name')
        self.classification = record.get('classification_name')
        self.family = record.get('family_name')
        self.genus = record.get('genus_name')
        self.species = record.get('species_name')
        self.breed = record.get('breed_name')
        self.breed_kana = record.get('breed_name_kana')
        self.natural_monument = record.get('breed_name_kana')
        self.breed_tag = record.get('breed_tag')

    def get_hierarchy(self) -> tuple:
        """
        linked_list用 のタプルを返す

        Returns: list
        """
        return self.kingdom, self.phylum, self.classification, self.family, self.genus, self.species, self.breed
