from unittest import TestCase

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.valueobject.taxonomy_hierarchy import TaxonomyHierarchyItem
from taxonomy.domain.valueobject.taxonomy_graph import TaxonomyGraph


class TaxonomyGraphTest(TestCase):
    def test_builds_nodes_and_edges_from_breed_entities(self):
        """
        シナリオ:
        - 入力: 同じ上位階層を共有する2件の品種Entity。
        - 処理: TaxonomyGraph.from_breed_entities を呼び出す。
        - 期待値: 上位階層ノードは重複せず、品種までの親子edgeが生成されること。
        """
        breed_entities = [
            BreedEntity(
                {
                    "kingdom_id": 1,
                    "kingdom_name": "動物界",
                    "phylum_id": 2,
                    "phylum_name": "脊索動物門",
                    "classification_id": 3,
                    "classification_name": "鳥綱",
                    "family_id": 4,
                    "family_name": "キジ科",
                    "genus_id": 5,
                    "genus_name": "ヤケイ属",
                    "species_id": 6,
                    "species_name": "セキショクヤケイ種",
                    "breed_id": 7,
                    "breed_name": "ボリスブラウン",
                    "breed_name_kana": "ボリスブラウン",
                    "natural_monument_name": None,
                    "breed_tag": None,
                }
            ),
            BreedEntity(
                {
                    "kingdom_id": 1,
                    "kingdom_name": "動物界",
                    "phylum_id": 2,
                    "phylum_name": "脊索動物門",
                    "classification_id": 3,
                    "classification_name": "鳥綱",
                    "family_id": 4,
                    "family_name": "キジ科",
                    "genus_id": 5,
                    "genus_name": "ヤケイ属",
                    "species_id": 6,
                    "species_name": "セキショクヤケイ種",
                    "breed_id": 8,
                    "breed_name": "アローカナ",
                    "breed_name_kana": "アローカナ",
                    "natural_monument_name": None,
                    "breed_tag": None,
                }
            ),
        ]

        graph = TaxonomyGraph.from_breed_entities(
            breed_entities,
            {7: "/taxonomy/breeds/7/", 8: "/taxonomy/breeds/8/"},
        )

        payload = graph.to_payload()
        nodes = {node["id"]: node for node in payload["nodes"]}
        edges = {(edge["source"], edge["target"]) for edge in payload["edges"]}
        self.assertEqual(9, len(nodes))
        self.assertEqual(
            {
                "id": "breed:7",
                "name": "ボリスブラウン",
                "rank": "breed",
                "detail_url": "/taxonomy/breeds/7/",
            },
            nodes["breed:7"],
        )
        self.assertIn(("root:root", "kingdom:1"), edges)
        self.assertIn(("species:6", "breed:7"), edges)
        self.assertIn(("species:6", "breed:8"), edges)

    def test_builds_fallback_ids_when_source_ids_are_missing(self):
        """
        シナリオ:
        - 入力: DB由来のIDを持たない品種Entity。
        - 処理: TaxonomyGraph.from_breed_entities を呼び出す。
        - 期待値: 階層パスを使った一意なfallback IDで nodes/edges が生成されること。
        """
        breed_entity = BreedEntity(
            {
                "kingdom_name": "動物界",
                "phylum_name": "環形動物門",
                "classification_name": "貧毛綱",
                "family_name": "ツリミミズ科",
                "genus_name": "シマミミズ属",
                "species_name": "シマミミズ種",
                "breed_name": "シマミミズ",
                "breed_name_kana": "シマミミズ",
                "natural_monument_name": None,
                "breed_tag": "コンポスト",
            }
        )

        graph = TaxonomyGraph.from_breed_entities([breed_entity])

        payload = graph.to_payload()
        node_ids = {node["id"] for node in payload["nodes"]}
        self.assertIn("kingdom:動物界", node_ids)
        self.assertIn(
            "breed:動物界/環形動物門/貧毛綱/ツリミミズ科/シマミミズ属/シマミミズ種/シマミミズ",
            node_ids,
        )

    def test_breed_entity_returns_hierarchy_items_as_value_objects(self):
        """
        シナリオ:
        - 入力: phylum_id と phylum_name を持つ品種Entity。
        - 処理: get_taxonomy_items を呼び出す。
        - 期待値: id/name/rank が TaxonomyHierarchyItem として返されること。
        """
        breed_entity = BreedEntity(
            {
                "kingdom_id": 1,
                "kingdom_name": "動物界",
                "phylum_id": 2,
                "phylum_name": "脊索動物門",
                "classification_id": 3,
                "classification_name": "鳥綱",
                "family_id": 4,
                "family_name": "キジ科",
                "genus_id": 5,
                "genus_name": "ヤケイ属",
                "species_id": 6,
                "species_name": "セキショクヤケイ種",
                "breed_id": 7,
                "breed_name": "ボリスブラウン",
                "breed_name_kana": "ボリスブラウン",
                "natural_monument_name": None,
                "breed_tag": None,
            }
        )

        taxonomy_items = breed_entity.get_taxonomy_items()

        self.assertEqual(
            TaxonomyHierarchyItem("phylum", 2, "脊索動物門"),
            taxonomy_items[1],
        )
