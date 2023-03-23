from typing import Self

from taxonomy.domain.breed_entity import BreedEntity


class Node:
    """
    See Also: https://www.pythonforbeginners.com/lists/linked-list-in-python
    See Also: https://engineeringnote.hateblo.jp/entry/python/algorithm-and-data-structures/multi_list_structure
    """
    _name: str
    _children: list[Self]

    def __init__(self, name):
        self._name = name
        self._children = list()

    @property
    def name(self):
        return self._name

    def exists_child(self, needle: str) -> bool:
        """
        needle の名前の子Nodeを持っているか

        Args:
            needle: str

        Returns: bool
        """
        return not not self.get_child(needle)

    def list(self) -> list:
        return self._children

    def add_child(self, node: Self) -> Self:
        """
        _children に node がいないことを確認してから追加する

        Args:
            node: 追加したいNode
        """
        if not self.exists_child(node.name):
            self._children.append(node)

        return self

    def get_child(self, needle: str) -> Self:
        """
        _children に needle がいるかを判定し、いたらその Node を返す

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
