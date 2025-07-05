from soil_analysis.domain.valueobject.kml import KmlDocumentVO, KmlPlacemarkVO
from soil_analysis.domain.valueobject.land import LandLocation


class KmlService:
    @staticmethod
    def parse_kml(kml_str: str) -> list[LandLocation]:
        """
        KML形式の文字列を解析して圃場位置情報のリストを作成します。

        Args:
            kml_str (str): KML形式の文字列データ

        Returns:
            list[LandLocation]: 解析された圃場位置情報のリスト

        Raises:
            ValueError: 不正なKML形式の文字列が指定された場合
        """
        try:
            # KML文書の前処理と検証
            kml_document_vo = KmlDocumentVO(kml_str)
            kml_document = kml_document_vo.to_kml_object()

            # 各Placemarkを処理
            land_locations = []
            for feature in kml_document.features:
                placemark_vo = KmlPlacemarkVO(feature)
                land_locations.append(
                    LandLocation(placemark_vo.coordinates, placemark_vo.name)
                )

            return land_locations

        except ValueError as e:
            raise ValueError("Invalid KML format") from e
