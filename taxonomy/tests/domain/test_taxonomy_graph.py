from unittest import TestCase

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.valueobject.taxonomy_hierarchy import (
    TaxonomyHierarchy,
    TaxonomyHierarchyItem,
)
from taxonomy.domain.valueobject.taxonomy_graph import TaxonomyGraph


class TaxonomyGraphTest(TestCase):
    def _build_chicken_hierarchy(self, breed: TaxonomyHierarchyItem):
        return [
            TaxonomyHierarchyItem("kingdom", 1, "動物界"),
            TaxonomyHierarchyItem("phylum", 2, "脊索動物門"),
            TaxonomyHierarchyItem("classification", 3, "鳥綱"),
            TaxonomyHierarchyItem("family", 4, "キジ科"),
            TaxonomyHierarchyItem("genus", 5, "ヤケイ属"),
            TaxonomyHierarchyItem("species", 6, "セキショクヤケイ種"),
            breed,
        ]

    def test_builds_nodes_and_edges_from_breed_entities(self):
        """
        シナリオ:
        - 入力: 同じ上位階層を共有する2件の品種Entity。
        - 処理: TaxonomyGraph.from_breed_entities を呼び出す。
        - 期待値: 上位階層ノードは重複せず、品種までの親子edgeが生成されること。
        """
        breed_entities = [
            BreedEntity.from_hierarchy_items(
                self._build_chicken_hierarchy(
                    TaxonomyHierarchyItem("breed", 7, "ボリスブラウン")
                ),
                breed_kana="ボリスブラウン",
            ),
            BreedEntity.from_hierarchy_items(
                self._build_chicken_hierarchy(
                    TaxonomyHierarchyItem("breed", 8, "アローカナ")
                ),
                breed_kana="アローカナ",
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
        breed_entity = BreedEntity.from_hierarchy_items(
            [
                TaxonomyHierarchyItem("kingdom", None, "動物界"),
                TaxonomyHierarchyItem("phylum", None, "環形動物門"),
                TaxonomyHierarchyItem("classification", None, "貧毛綱"),
                TaxonomyHierarchyItem("family", None, "ツリミミズ科"),
                TaxonomyHierarchyItem("genus", None, "シマミミズ属"),
                TaxonomyHierarchyItem("species", None, "シマミミズ種"),
                TaxonomyHierarchyItem("breed", None, "シマミミズ"),
            ],
            breed_kana="シマミミズ",
            breed_tag="コンポスト",
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
        - 入力: phylum を TaxonomyHierarchyItem として持つ品種Entity。
        - 処理: get_taxonomy_items を呼び出す。
        - 期待値: id/name/rank が TaxonomyHierarchyItem として返されること。
        """
        breed_entity = BreedEntity.from_hierarchy_items(
            self._build_chicken_hierarchy(
                TaxonomyHierarchyItem("breed", 7, "ボリスブラウン")
            ),
            breed_kana="ボリスブラウン",
        )

        taxonomy_items = breed_entity.get_taxonomy_items()

        self.assertEqual(
            TaxonomyHierarchyItem("phylum", 2, "脊索動物門"),
            taxonomy_items[1],
        )

    def test_taxonomy_hierarchy_rejects_wrong_rank_order(self):
        """
        シナリオ:
        - 入力: phylum と kingdom の順序が逆になった分類階層VO。
        - 処理: TaxonomyHierarchy.from_items を呼び出す。
        - 期待値: 分類階層の順序違いとして ValueError が発生すること。
        """
        hierarchy_items = [
            TaxonomyHierarchyItem("phylum", 2, "脊索動物門"),
            TaxonomyHierarchyItem("kingdom", 1, "動物界"),
            TaxonomyHierarchyItem("classification", 3, "鳥綱"),
            TaxonomyHierarchyItem("family", 4, "キジ科"),
            TaxonomyHierarchyItem("genus", 5, "ヤケイ属"),
            TaxonomyHierarchyItem("species", 6, "セキショクヤケイ種"),
            TaxonomyHierarchyItem("breed", 7, "ボリスブラウン"),
        ]

        with self.assertRaises(ValueError):
            TaxonomyHierarchy.from_items(hierarchy_items)
