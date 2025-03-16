from abc import ABC, abstractmethod


class BaseCoord(ABC):
    """座標を表現する抽象基底クラス

    緯度(latitude)と経度(longitude)を保持しますが、
    メソッドの戻り値での順序はサブクラスによって異なります。

    Attributes:
        latitude (float): 緯度（北緯がプラス、南緯がマイナス）
        longitude (float): 経度（東経がプラス、西経がマイナス）
    """

    def __init__(self, latitude: float, longitude: float):
        """座標オブジェクトを初期化します

        Args:
            latitude (float): 緯度（例: 34.7443565）
            longitude (float): 経度（例: 137.6489657）
        """
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
    """Google Maps 用の座標表現クラス

    Google Maps では (緯度,経度) の順序で座標を表します。
    例: 34.7443565,137.6489657

    順序の覚え方: Google Mapsでは「緯度,経度」(latitude,longitude)の順
    """

    def to_tuple(self) -> tuple[float, float]:
        """Google Maps形式のタプル (緯度,経度) を返します

        Returns:
            tuple[float, float]: (緯度,経度)の順のタプル
        """
        return self.latitude, self.longitude

    def to_str(self) -> str:
        """Google Maps形式の文字列 "緯度,経度" を返します

        Returns:
            str: "緯度,経度"の形式の文字列
        """
        return f"{self.latitude},{self.longitude}"


class XarvioCoord(BaseCoord):
    """Xarvio 用の座標表現クラス

    Xarvio では (経度,緯度) の順序で座標を表します。
    例: 137.6489657,34.7443565

    順序の覚え方: Xarvio では「経度,緯度」(longitude,latitude)の順（Google Mapsと逆）
    """

    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude},{self.latitude}"

    def to_google(self) -> GoogleMapsCoord:
        return GoogleMapsCoord(latitude=self.latitude, longitude=self.longitude)
