from typing import List

from haversine import haversine, Unit

from lib.geo.valueobject.coord import CaptureLocationCoords, LandCoords
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import Land
from soil_analysis.domain.valueobject.landcandidates import LandCandidates
from soil_analysis.domain.valueobject.photo.androidphoto import AndroidPhoto


class PhotoProcessingService:
    def process_photos(
        self, photosfolder: List[str], land_candidates: LandCandidates
    ) -> List[str]:
        processed_photos = []

        # あるフォルダのn個の写真を処理
        for photopath in photosfolder:
            # IMG20230630190442.jpg のようなファイル名になっている
            android_photo = AndroidPhoto(photopath)
            # 画像（＝撮影位置）から最も近い圃場を特定
            nearest_land = self.find_nearest_land(
                android_photo.location, land_candidates
            )

            # TODO: ここで写真のリネーム処理やoutputfolderへの保存などの操作を行う

            processed_photos.append(photopath)

        return processed_photos

    def find_nearest_land(
        self, photo_coords: CaptureLocation, land_candidates: LandCandidates
    ) -> Land:
        """
        n個圃場の距離をそれぞれ調べていちばん距離の近い圃場を特定します
        :param photo_coords:
        :param land_candidates:
        :return:
        """
        min_distance = float("inf")
        nearest_land = None

        for land in land_candidates.list():
            distance = self.calculate_distance(photo_coords.corrected, land.center)
            if distance < min_distance:
                min_distance = distance
                nearest_land = land

        return nearest_land

    @staticmethod
    def calculate_distance(
        coords1: CaptureLocationCoords, coords2: LandCoords, unit: str = Unit.METERS
    ) -> float:
        """
        他の座標との距離を計算します。
        xarvio は 経度緯度(lng,lat) をエクスポートする
        haversineライブラリは 緯度経度(lat,lng) を2セット受け入れて距離を測る
        そのため、haversineライブラリを使うタイミングでタプルを逆にしている

        :param coords1: 座標1
        :param coords2: 座標2
        :param unit: 距離の単位（'km'、'miles'、'm'など）
        :return: 距離（単位に応じた値）
        """
        return haversine(
            coords1.to_google().to_tuple(),
            coords2.to_google().to_tuple(),
            unit=unit,
        )
