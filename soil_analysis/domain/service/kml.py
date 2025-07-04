from fastkml import kml
from fastkml.features import Placemark

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

        Notes:
            xarvioなら以下でOK
            upload_file: InMemoryUploadedFile = self.request.FILES['file']
            kml_raw = upload_file.read()
            kml_service = KmlService()

            fastkmlライブラリについて:
            - kml_document.featuresはList[_Feature]を返すが、実際の要素はPlacemarkオブジェクト
            - _Featureは抽象基底クラスで、Placemarkは_FeatureのDirect known subclass
            - geometry属性はPlacemark固有のため、型キャストが必要
            - このキャストは安全（実際の要素はPlacemarkインスタンス）

            XML宣言の処理について:
            - lxmlライブラリは文字列（str）にXML宣言が含まれていると処理できない
            - "Unicode strings with encoding declaration are not supported" エラーが発生
            - 実際のKMLファイルにはXML宣言が含まれることが多いため、前処理で除去

        Returns:
            list[LandLocation]: 解析された圃場位置情報のリスト。

        Raises:
            ValueError: 不正なKML形式の文字列が指定された場合に発生します。
        """
        land_location_list: list[LandLocation] = []

        try:
            # XML宣言を除去（lxmlの制限回避）
            clean_kml_str = kml_str
            if kml_str.strip().startswith('<?xml'):
                # XML宣言行を除去
                lines = kml_str.strip().split('\n')
                clean_kml_str = '\n'.join(line for line in lines if not line.strip().startswith('<?xml'))

            # namespace宣言がない場合は追加（xarvio対応）
            if '<kml>' in clean_kml_str and 'xmlns=' not in clean_kml_str:
                clean_kml_str = clean_kml_str.replace('<kml>', '<kml xmlns="https://www.opengis.net/kml/2.2">')

            kml_doc = kml.KML.from_string(clean_kml_str)
            features_list = list(kml_doc.features)

            # featuresが空でないことを確認
            if not features_list:
                raise ValueError("No features found in KML document")

            kml_document = features_list[self.KML_DOCUMENT]

            for feature in kml_document.features:
                # _FeatureからPlacemarkへの型キャスト（安全：実際の要素はPlacemarkインスタンス）
                place_mark: Placemark = feature  # type: ignore
                place_mark_object = place_mark.geometry
                name = place_mark.name

                # geoms属性がgeneratorを返すため、リストに変換してからアクセス
                geoms = list(place_mark_object.geoms)
                if geoms:
                    # リストの最初の要素にアクセス
                    first_geom = geoms[0]

                    # ジオメトリの型によって座標の取得方法を変更
                    if hasattr(first_geom, 'exterior'):
                        # Polygonの場合
                        coord_str = self.to_str(list(first_geom.exterior.coords))
                    else:
                        # Pointの場合
                        coord_str = self.to_str(list(first_geom.coords))

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
