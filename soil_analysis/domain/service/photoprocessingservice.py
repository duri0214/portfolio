from haversine import haversine, Unit

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation
from soil_analysis.domain.valueobject.landcandidates import LandCandidates
from soil_analysis.domain.valueobject.photo.androidphoto import AndroidPhoto


class PhotoProcessingService:
    def process_photos(
        self, folder_path_list: list[str], land_candidates: LandCandidates
    ) -> list[str]:
        processed_photos = []

        # あるフォルダのn個の写真を処理
        for folder_path in folder_path_list:
            # IMG20230630190442.jpg のようなファイル名になっている
            android_photo = AndroidPhoto(folder_path)
            # 画像（＝撮影位置）から最も近い圃場を特定
            nearest_land = self.find_nearest_land(
                android_photo.location, land_candidates
            )

            # TODO: ここで写真のリネーム処理や output_folder への保存などの操作を行う

            processed_photos.append(folder_path)

        return processed_photos

    def find_nearest_land(
        self, photo_coord: CaptureLocation, land_candidates: LandCandidates
    ) -> LandLocation:
        """撮影位置から最も近い圃場を特定します。

        カメラの方向に調整された位置を使用して、より正確に撮影対象の圃場を特定します。

        Args:
            photo_coord: 撮影位置情報（方位角による調整を含む）
            land_candidates: 検索対象の圃場リスト

        Returns:
            LandLocation: 最も近いと判断された圃場
        """
        min_distance = float("inf")
        nearest_land = None

        for land in land_candidates.list():
            # 調整された位置から各圃場までの距離を計算
            distance = self.calculate_distance(
                photo_coord.adjusted_position, land.center
            )
            if distance < min_distance:
                min_distance = distance
                nearest_land = land

        return nearest_land

    @staticmethod
    def calculate_distance(
        coord1: XarvioCoord, coord2: LandLocation, unit: str = Unit.METERS
    ) -> float:
        """
        他の座標との距離を計算します。
        xarvio は 経度緯度(lng,lat) をエクスポートする
        haversineライブラリは 緯度経度(lat,lng) を2セット受け入れて距離を測る
        そのため、haversineライブラリを使うタイミングでタプルを逆にしている

        :param coord1: 座標1
        :param coord2: 座標2
        :param unit: 距離の単位（'km'、'miles'、'm'など）
        :return: 距離（単位に応じた値）
        """
        return haversine(
            coord1.to_google().to_tuple(),
            coord2.to_google().to_tuple(),
            unit=unit,
        )
