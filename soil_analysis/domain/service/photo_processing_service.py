from haversine import haversine, Unit

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.photo import AndroidPhoto
from soil_analysis.domain.valueobject.photo_land_association import PhotoLandAssociation
from soil_analysis.models import Land


class PhotoProcessingService:
    def process_photos(
        self, photo_path_list: list[str], land_list: list[Land]
    ) -> list[PhotoLandAssociation]:
        """写真パスのリストから写真を処理し、最寄りの圃場と紐づけます。

        Args:
            photo_path_list: 処理する写真ファイルのパスリスト
            land_list: 検索対象の圃場リスト

        Returns:
            list[PhotoLandAssociation]: 写真と圃場の紐づけ情報のリスト
        """
        associations = []

        # 複数の写真ファイルを処理
        for photo_path in photo_path_list:
            # IMG20230630190442.jpg のようなファイル名になっている
            android_photo = AndroidPhoto(photo_path)
            photo_location = android_photo.location

            # 画像（＝撮影位置）から最も近い圃場を特定
            nearest_land = self.find_nearest_land(photo_location, land_list)

            # 距離を計算
            distance = self.calculate_distance(
                photo_location.adjusted_position, nearest_land
            )

            # 写真と圃場の紐づけ情報を作成
            association = PhotoLandAssociation(photo_path, nearest_land, distance)
            associations.append(association)

            # TODO: ここで写真のリネーム処理や output_folder への保存などの操作を行う

        return associations

    def find_nearest_land(
        self, photo_coord: CaptureLocation, land_list: list[Land]
    ) -> Land:
        """撮影位置から最も近い圃場を特定します。

        写真のGPSメタデータから抽出した撮影位置を使用して、候補となる圃場の中から
        最も距離が近い圃場を特定します。カメラの方向情報が含まれている場合は、
        その方向に調整された位置を使用して、より正確に撮影対象の圃場を特定します。

        例えば、複数の隣接する圃場（A1、A2、A3など）を撮影した場合、各写真がどの圃場を
        対象としているかを自動的に判別することができます。

        Args:
            photo_coord: 撮影位置情報（方位角による調整を含む）
            land_list: 検索対象の圃場リスト

        Returns:
            Land: 最も近いと判断された圃場
        """
        min_distance = float("inf")
        nearest_land = None

        for land in land_list:
            distance = self.calculate_distance(photo_coord.adjusted_position, land)
            if distance < min_distance:
                min_distance = distance
                nearest_land = land

        return nearest_land

    @staticmethod
    def calculate_distance(
        photo_spot: XarvioCoord, land: Land, unit: str = Unit.METERS
    ) -> float:
        """２つの座標間の距離を計算します。

        xarvioは経度緯度(lng,lat)をエクスポートする一方、
        haversineライブラリは緯度経度(lat,lng)の2セットを受け取って距離を計算します。
        そのため、haversineライブラリを使用する際に座標のタプルを逆にしています。

        Args:
            photo_spot: 開始座標
            land: 終了座標
            unit: 距離の単位（デフォルトはメートル）

        Returns:
            float: 指定単位での2点間の距離
        """
        return haversine(
            photo_spot.to_google().to_tuple(),
            land.to_google().to_tuple(),
            unit=unit,
        )
