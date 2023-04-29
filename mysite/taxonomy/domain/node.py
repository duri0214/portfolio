from __future__ import annotations

from taxonomy.domain.breed_entity import BreedEntity


class Node:
    """
    See Also: https://www.pythonforbeginners.com/lists/linked-list-in-python
    See Also: https://engineeringnote.hateblo.jp/entry/python/algorithm-and-data-structures/multi_list_structure
    """
    _name: str
    _children: list[Node]

    def __init__(self, name: str):
        self._name = name
        self._children = list()

    @property
    def name(self) -> str:
        return self._name

    def exists_child(self, needle: str) -> bool:
        """
        needle の名前の子Nodeを持っているか

        Args:
            needle: str

        Returns: bool
        """
        return not not self.get_child(needle)

    def list(self) -> list[Node]:
        return self._children

    def add_child(self, node: 'Node'):
        """
        _children に node がいないことを確認してから追加する
        TODO: return の戻り型をSelf（3.11+）

        Args:
            node: 追加したいNode
        """
        if not self.exists_child(node.name):
            self._children.append(node)

        return self

    def get_child(self, needle: str):
        """
        _children に needle がいるかを判定し、いたらその Node を返す
        TODO: return の戻り型をSelf（3.11+）

        Args:
            needle: 探したい Node._name
        """
        return_value = None
        node: Node
        for node in self._children:
            if node._name == needle:
                return_value = node
                break

        return return_value


class NodeTree:
    _tree: Node

    def __init__(self, records: list[BreedEntity], name: str = 'root'):
        self._tree = Node(name)
        self._breed_entities = records

        for breed_entity in self._breed_entities:
            self._recurcive_add(self._tree, breed_entity.get_taxonomies())

    def _recurcive_add(self, anchor: Node, taxonomies: list):
        taxonomy = taxonomies.pop(0)
        child = anchor.add_child(Node(taxonomy)).get_child(taxonomy)
        if taxonomies:
            self._recurcive_add(child, taxonomies)

    def _recurcive_convert(self, anchor: Node) -> dict:
        converted = []
        if len(anchor.list()) > 0:
            for child in anchor.list():
                converted.append(self._recurcive_convert(child))

        return {"name": anchor.name, "children": converted}

    def export(self) -> dict:
        return self._recurcive_convert(self._tree)
