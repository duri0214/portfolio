from fastkml import kml

from soil_analysis.domain.valueobject.land import LandLocation


class KmlService:
    KML_DOCUMENT = 0
    KML_POLYGON = 0
    KML_LNG = 0
    KML_LAT = 1

    def parse_kml(self, kml_str):
        """
        KML形式の文字列を解析して 圃場位置情報のリスト を作成します。

        Args:
            kml_str (str): KML形式の文字列データ。

        Notes: xarvioなら以下でOK
            upload_file: InMemoryUploadedFile = self.request.FILES['file']
            kml_raw = upload_file.read()
            kml_service = KmlService()

        Returns:
            list[LandLocation]: 解析された圃場位置情報のリスト。

        Raises:
            ValueError: 不正なKML形式の文字列が指定された場合に発生します。
        """
        land_location_list: list[LandLocation] = []

        try:
            kml_doc = kml.KML()
            kml_doc.from_string(kml_str)
            kml_document = list(kml_doc.features())[self.KML_DOCUMENT]

            for place_mark in kml_document.features():
                place_mark_object = place_mark.geometry
                name = place_mark.name
                coord_str = self.to_str(
                    place_mark_object.geoms[self.KML_POLYGON].exterior.coords
                )
                land_location_list.append(LandLocation(coord_str, name))

            return land_location_list
        except ValueError as e:
            raise ValueError("Invalid KML format") from e

    def to_str(self, coord_list: list):
        """
        座標のリストを文字列表現に変換します。

        Args:
            coord_list (list): 座標のリスト。各座標はタプルとして表されます。

        Returns:
            str: 座標の文字列表現。
        """
        return " ".join(
            [f"{coord[self.KML_LNG]},{coord[self.KML_LAT]}" for coord in coord_list]
        )
