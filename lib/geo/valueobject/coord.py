from abc import ABC, abstractmethod


class BaseCoord(ABC):
    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude

    @abstractmethod
    def to_tuple(self) -> tuple[float, float]:
        """
        座標をタプル形式で取得します。具体的な順序はサブクラスによります。

        Returns:
            tuple[float, float]: 座標を表すタプル
        """
        pass

    @abstractmethod
    def to_str(self) -> str:
        """
        座標を文字列形式で取得します。具体的な順序はサブクラスによります。

        Returns:
            str: 座標を表す文字列
        """
        pass


class GoogleMapsCoord(BaseCoord):
    """
    Google Maps 用の座標変換クラス。BaseCoordを継承します。 (緯度,経度)です。
    """

    def to_tuple(self) -> tuple[float, float]:
        return self.latitude, self.longitude

    def to_str(self) -> str:
        return f"{self.latitude},{self.longitude}"


class XarvioCoord(BaseCoord):
    """
    Capture Location 用の座標変換クラス。BaseCoordを継承します。
    xarvio用に作ったので、順序が Google Maps とは異なり、(経度,緯度)です。
    """

    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude},{self.latitude}"

    def to_google(self) -> GoogleMapsCoord:
        return GoogleMapsCoord(self.latitude, self.longitude)
