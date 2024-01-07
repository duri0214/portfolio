from abc import ABC, abstractmethod


class BaseGraphEngine(ABC):
    """グラフ処理を定義するための基底クラス"""

    @abstractmethod
    def plot_graph(self, *args):
        pass
