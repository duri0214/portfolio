from dataclasses import dataclass

from taxonomy.domain.breed_entity import BreedEntity
from taxonomy.domain.valueobject.taxonomy_hierarchy import TAXONOMY_HIERARCHY_RANKS


TAXONOMY_GRAPH_ROOT_RANK = "root"
TAXONOMY_GRAPH_RANK_DEPTHS = {
    TAXONOMY_GRAPH_ROOT_RANK: 0,
    **{rank: index for index, rank in enumerate(TAXONOMY_HIERARCHY_RANKS, start=1)},
}


@dataclass(frozen=True)
class TaxonomyGraphNode:
    """
    分類グラフの1ノードを表すValue Object。

    Attributes:
        id: グラフ内で一意になるノードID。
        name: 画面表示や検索に使う分類名。
        rank: root、kingdom、phylum などの階層種別。
        depth: rootを0とした分類階層の深さ。
        detail_url: 詳細ページへ遷移できる場合のURL。
    """

    id: str
    name: str
    rank: str
    depth: int
    detail_url: str = ""

    @classmethod
    def create(
        cls, id: str, name: str, rank: str, detail_url: str = ""
    ) -> "TaxonomyGraphNode":
        return cls(
            id=id,
            name=name,
            rank=rank,
            depth=TAXONOMY_GRAPH_RANK_DEPTHS[rank],
            detail_url=detail_url,
        )

    def to_payload(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "name": self.name,
            "rank": self.rank,
            "depth": self.depth,
            "detail_url": self.detail_url,
        }


@dataclass(frozen=True)
class TaxonomyGraphEdge:
    """
    分類グラフの親子関係を表すValue Object。

    Attributes:
        source: 親ノードID。
        target: 子ノードID。
        relation: source と target の関係種別。
    """

    source: str
    target: str
    relation: str = "parent-child"

    def to_payload(self) -> dict[str, str]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
        }


@dataclass(frozen=True)
class TaxonomyGraph:
    """
    nodes/edges 形式の分類グラフ構造を表すValue Object。

    Attributes:
        nodes: グラフに含まれるノード。
        edges: ノード同士の親子関係。
    """

    nodes: tuple[TaxonomyGraphNode, ...]
    edges: tuple[TaxonomyGraphEdge, ...]

    @classmethod
    def from_breed_entities(
        cls,
        breed_entities: list[BreedEntity],
        breed_detail_urls: dict[int, str] | None = None,
        root_name: str = "root",
    ) -> "TaxonomyGraph":
        """
        BreedEntity の分類階層から nodes/edges 形式のグラフを生成する。

        Args:
            breed_entities: 分類階層を持つ品種Entityのリスト。
            breed_detail_urls: breed_id をキーにした詳細ページURL。
            root_name: グラフの起点になるrootノード名。

        Returns:
            分類階層を親子関係として表した TaxonomyGraph。
        """
        detail_urls = breed_detail_urls or {}
        nodes_by_id = {
            "root:root": TaxonomyGraphNode.create(
                id="root:root",
                name=root_name,
                rank=TAXONOMY_GRAPH_ROOT_RANK,
            )
        }
        edges_by_key: dict[tuple[str, str], TaxonomyGraphEdge] = {}

        for breed_entity in breed_entities:
            parent_id = "root:root"
            fallback_path: list[str] = []
            for item in breed_entity.get_taxonomy_items():
                if not item.has_name:
                    continue

                name = item.name
                rank = item.rank
                source_id = item.source_id
                fallback_path.append(name)
                node_id = cls._build_node_id(rank, source_id, fallback_path)
                if node_id not in nodes_by_id:
                    detail_url = ""
                    if rank == "breed" and isinstance(source_id, int):
                        detail_url = detail_urls.get(source_id, "")
                    nodes_by_id[node_id] = TaxonomyGraphNode.create(
                        id=node_id,
                        name=name,
                        rank=rank,
                        detail_url=detail_url,
                    )

                edge_key = (parent_id, node_id)
                edges_by_key.setdefault(
                    edge_key,
                    TaxonomyGraphEdge(source=parent_id, target=node_id),
                )
                parent_id = node_id

        return cls(
            nodes=tuple(nodes_by_id.values()),
            edges=tuple(edges_by_key.values()),
        )

    @staticmethod
    def _build_node_id(
        rank: str, source_id: int | str | None, fallback_path: list[str]
    ) -> str:
        if source_id is not None:
            return f"{rank}:{source_id}"

        return f"{rank}:{'/'.join(fallback_path)}"

    def to_payload(self) -> dict[str, list[dict[str, str | int]]]:
        return {
            "nodes": [node.to_payload() for node in self.nodes],
            "edges": [edge.to_payload() for edge in self.edges],
        }
