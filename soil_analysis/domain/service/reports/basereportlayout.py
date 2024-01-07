from abc import ABC, abstractmethod


class BaseReportLayout(ABC):
    """レポートを定義するための基底クラス"""

    @abstractmethod
    def publish(self, *args):
        pass
