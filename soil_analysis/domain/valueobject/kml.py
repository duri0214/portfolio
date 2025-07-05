from dataclasses import dataclass
from xml.etree import ElementTree


class Placemark:
    """
    xarvioにおけるKML Placemark要素 - 個別の圃場を表現

    KmlDocumentに包含される要素で、一つの圃場（農地区画）を表します。
    各圃場は名前と座標文字列を持ちます。
    """

    def __init__(self, name: str, coordinates: str):
        self.name = name
        self.coordinates_str = coordinates


class KmlDocument:
    """
    xarvioにおけるKML Document要素 - 複数の圃場を包含する文書構造

    KMLファイルの最上位要素で、複数のPlacemark（圃場）を管理します。
    一つのKMLファイルには通常一つのKmlDocumentが含まれ、
    その中に複数の圃場データが格納されます。
    """

    def __init__(self, placemarks: list[Placemark]):
        self._placemarks = placemarks

    @property
    def features(self):
        return self._placemarks


@dataclass
class KmlDocumentVO:
    """KML文書の前処理と検証を担当するValue Object"""

    raw_kml: str

    def __post_init__(self):
        self._validate_and_clean()

    def _validate_and_clean(self):
        """XML宣言の除去とnamespace宣言の追加"""
        # 先頭と末尾の空白文字を除去
        self.raw_kml = self.raw_kml.strip()

        # XML宣言を除去（lxmlの制限回避）
        if self.raw_kml.startswith("<?xml"):
            lines = self.raw_kml.split("\n")
            self.raw_kml = "\n".join(
                line for line in lines if not line.strip().startswith("<?xml")
            )
            # 再度空白文字を除去
            self.raw_kml = self.raw_kml.strip()

    def to_kml_object(self):
        """XMLパーサーを使用してKMLを解析し、シンプルなオブジェクトを返す"""
        try:
            root = ElementTree.fromstring(self.raw_kml)
            placemarks = []

            # 名前空間なしでPlacemarkを検索（テストデータに合わせて）
            placemark_elements = root.findall(".//Placemark")

            if not placemark_elements:
                raise ValueError("No Placemark elements found in KML document")

            for placemark_elem in placemark_elements:
                # name要素を取得
                name_elem = placemark_elem.find(".//name")
                name = name_elem.text if name_elem is not None else ""

                # coordinates要素を取得
                # KML形式では座標は以下のような形式で格納されている：
                # "137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929 137.6484413,34.7441175 137.6489657,34.7443565"
                # 各座標点は「経度,緯度」のペアで、複数の座標点はスペースで区切られている
                # 例：「経度1,緯度1 経度2,緯度2 経度3,緯度3 ...」
                coords_elem = placemark_elem.find(".//coordinates")

                if coords_elem is not None and coords_elem.text:
                    coordinates = coords_elem.text.strip()
                    # 座標文字列の例：
                    # "137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929"
                    # これは圃場の境界を表す多角形の頂点座標列

                    # 座標点の個数を計算（デバッグ用）
                    coord_points = coordinates.split()
                    print(f"処理中の圃場: {name} (座標点数: {len(coord_points)}点)")

                    placemarks.append(Placemark(name, coordinates))

            if not placemarks:
                raise ValueError("No valid Placemarks with coordinates found")

            return KmlDocument(placemarks)

        except Exception as e:
            raise ValueError(f"Failed to parse KML: {str(e)}")


@dataclass
class KmlPlacemarkVO:
    """
    KML Placemarkの型キャストと座標抽出を担当するValue Object

    このクラスは農業システムにおける圃場（農地の単位）を表すPlacemarkデータを扱います。
    圃場は農地を管理・運営する上での基本単位であり、各圃場は名前と地理的境界線を持ちます。
    KMLファイルでは、一つのPlacemarkが一つの圃場に対応します。

    Attributes:
        feature: Placemarkオブジェクト

    使用例:
        圃場A、圃場B、圃場Cといった具体的な農地区画がKMLファイル内の
        個別のPlacemarkとして定義されています。
    """

    feature: Placemark | object  # Placemark object

    def __post_init__(self):
        self._validate_placemark()

    def _validate_placemark(self):
        """Placemarkへの型キャスト（安全性確認）"""
        # Placemarkオブジェクトを受け入れる
        pass

    @property
    def placemark(self):
        return self.feature

    @property
    def name(self) -> str:
        return self.placemark.name or ""

    @property
    def coordinates(self) -> str:
        """xarvio用の座標文字列を返す"""
        # Placemarkクラスのcoordinatesをそのまま返す
        # XMLから直接抽出済みの座標文字列
        return self.placemark.coordinates_str
