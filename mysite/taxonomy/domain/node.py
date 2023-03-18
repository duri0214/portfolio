from typing import Self


class Node:
    """
    See Also: https://www.pythonforbeginners.com/lists/linked-list-in-python
    See Also: https://engineeringnote.hateblo.jp/entry/python/algorithm-and-data-structures/multi_list_structure
    """
    _name: str
    _children: list[Self]

    def __init__(self, name):
        self._name = name

        # TODO: ここを解決しないと...
        #  1. クラス変数はクラス生成時以降は初期化されないからinstanceを無視してずっと増えてしまう https://coush.jp/280.html
        #  2. ここで初期化すると loop 2回目以降でずっと初期化される（蓄積できない） test参考
        self._children = list()

    @property
    def name(self):
        return self._name

    def _exists(self, needle: Self):
        node: Node
        return not not [node for node in self._children if node.name == needle.name]

    def list(self) -> list:
        return self._children

    def add_child(self, node: Self) -> Self:
        """
        _children に node がいないことを確認してから追加する

        Args:
            node: 追加したいNode
        """
        if not self._exists(node):
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
