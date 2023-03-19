from unittest import TestCase

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import Node


class TestNode(TestCase):
    def setUp(self) -> None:
        self.data = [
            {
                'kingdom_name': '動物界', 'phylum_name': '環形動物門', 'classification_name': '貧毛綱', 'family_name': 'ツリミミズ科',
                'genus_name': 'シマミミズ属', 'species_name': 'シマミミズ種', 'breed_name': 'シマミミズ', 'breed_name_kana': 'シマミミズ',
                'natural_monument_name': None, 'breed_tag': 'コンポスト'
            },
            {
                'kingdom_name': '動物界', 'phylum_name': '脊椎動物門', 'classification_name': '鳥綱', 'family_name': 'キジ科',
                'genus_name': 'ヤケイ属', 'species_name': 'セキショクヤケイ種', 'breed_name': 'ボリスブラウン',
                'breed_name_kana': 'アメラウカナ', 'natural_monument_name': None, 'breed_tag': None
            },
        ]
        self.breed_entities = [BreedEntity(x) for x in self.data]

    def test_add_child_can_added(self):
        kingdom = Node('動物界')
        self.assertEqual(0, len(kingdom.list()))
        kingdom.add_child(Node('環形動物門'))
        kingdom.add_child(Node('脊椎動物門'))
        self.assertEqual(2, len(kingdom.list()))

    def test_add_child_cant_add_same_instance(self):
        kingdom = Node('動物界')
        kingdom.add_child(Node('脊椎動物門'))
        kingdom.add_child(Node('脊椎動物門'))
        self.assertEqual(1, len(kingdom.list()))

    def test_get_child_exists_same_addr_instance(self):
        kingdom = Node('動物界')
        target_node = Node('環形動物門')
        kingdom.add_child(target_node)
        kingdom.add_child(Node('脊椎動物門'))
        self.assertEqual(target_node, kingdom.get_child('環形動物門'))

    def test_add_child_hierarchical_add(self):
        root = Node('root')
        for breed_entity in self.breed_entities:
            kingdom = Node(breed_entity.kingdom)
            root.add_child(kingdom)
            phylum = Node(breed_entity.phylum)
            kingdom.add_child(phylum)
            classification = Node(breed_entity.classification)
            phylum.add_child(classification)
            family = Node(breed_entity.family)
            classification.add_child(family)
            genus = Node(breed_entity.genus)
            family.add_child(genus)
            species = Node(breed_entity.species)
            genus.add_child(species)
            breed = Node(breed_entity.breed)
            species.add_child(breed)

            # TODO: kingdomのinstanceアドレスがループごとに変わっていることを確認してください
            print(kingdom)

        # root（すべての界を束ねる収束点は1つの界をもつ →動物界）
        self.assertEqual('root', root.name)
        self.assertEqual(1, len(root.list()))
        kingdom = root.get_child('動物界')
        self.assertEqual('動物界', kingdom.name)
        # 環形動物門, 脊椎動物門
        # self.assertEqual(2, len(kingdom.list()))

        # ミミズレコードがあるかを点検
        phylum = kingdom.get_child('環形動物門')
        self.assertEqual('環形動物門', phylum.name)
        self.assertEqual(1, len(phylum.list()))
        classification = phylum.get_child('貧毛綱')
        self.assertEqual('貧毛綱', classification.name)
        self.assertEqual(1, len(classification.list()))
        family = classification.get_child('ツリミミズ科')
        self.assertEqual('ツリミミズ科', family.name)
        self.assertEqual(1, len(family.list()))
        genus = family.get_child('シマミミズ属')
        self.assertEqual('シマミミズ属', genus.name)
        self.assertEqual(1, len(genus.list()))
        species = genus.get_child('シマミミズ種')
        self.assertEqual('シマミミズ種', species.name)
        self.assertEqual(1, len(species.list()))
        breed = species.get_child('シマミミズ')
        self.assertEqual('シマミミズ', breed.name)
        self.assertEqual(0, len(breed.list()))

        # ニワトリレコードがあるかを点検
        phylum = kingdom.get_child('脊椎動物門')
        if phylum:
            self.assertEqual('脊椎動物門', phylum.name)  # TODO: 増えてないぞ？
            self.assertEqual(1, len(phylum.list()))
            classification = phylum.get_child('鳥綱')
            self.assertEqual('鳥綱', classification.name)
            self.assertEqual(1, len(classification.list()))
            family = classification.get_child('キジ科')
            self.assertEqual('キジ科', family.name)
            self.assertEqual(1, len(family.list()))
            genus = family.get_child('ヤケイ属')
            self.assertEqual('ヤケイ属', genus.name)
            self.assertEqual(1, len(genus.list()))
            species = genus.get_child('セキショクヤケイ種')
            self.assertEqual('セキショクヤケイ種', species.name)
            self.assertEqual(1, len(species.list()))
            breed = species.get_child('ボリスブラウン')
            self.assertEqual('ボリスブラウン', breed.name)
            self.assertEqual(0, len(breed.list()))
