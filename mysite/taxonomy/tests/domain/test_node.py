from unittest import TestCase

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.node import Node, NodeTree


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

    def test_name(self):
        self.assertEqual('abc', Node('abc').name)

    def test_exists_child(self):
        node = Node('abc')
        node.add_child(Node('def'))
        self.assertTrue(node.exists_child('def'))

    def test_get_child(self):
        node = Node('abc')
        node_def = Node('def')
        node.add_child(node_def)
        self.assertEqual(node_def, node.get_child('def'))

    def test_list(self):
        node_parent = Node('abc')
        node_def = Node('def')
        node_ghi = Node('ghi')
        node_parent.add_child(node_def)
        node_parent.add_child(node_ghi)
        self.assertEqual([node_def, node_ghi], node_parent.list())

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

    def test_node_tree(self):
        tree = NodeTree(self.breed_entities)
        expected = {
            "name": "root",
            "children": [
                {
                    "name": "動物界",
                    "children": [
                        {
                            "name": "環形動物門",
                            "children": [
                                {
                                    "name": "貧毛綱",
                                    "children": [
                                        {
                                            "name": "ツリミミズ科",
                                            "children": [
                                                {
                                                    "name": "シマミミズ属",
                                                    "children": [
                                                        {
                                                            "name": "シマミミズ種",
                                                            "children": [
                                                                {
                                                                    "name": "シマミミズ",
                                                                    "children": []
                                                                }
                                                            ]
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "name": "脊椎動物門",
                            "children": [
                                {
                                    "name": "鳥綱",
                                    "children": [
                                        {
                                            "name": "キジ科",
                                            "children": [
                                                {
                                                    "name": "ヤケイ属",
                                                    "children": [
                                                        {
                                                            "name": "セキショクヤケイ種",
                                                            "children": [
                                                                {
                                                                    "name": "ボリスブラウン",
                                                                    "children": []
                                                                }
                                                            ]
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        self.assertEqual(expected, tree.export())
