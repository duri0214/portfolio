from haversine import haversine, Unit

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation
from soil_analysis.domain.valueobject.landcandidates import LandCandidates
from soil_analysis.domain.valueobject.photo.androidphoto import AndroidPhoto


class PhotoProcessingService:
    def process_photos(
        self, photo_path_list: list[str], land_candidates: LandCandidates
    ) -> list[str]:
        """写真パスのリストから写真を処理し、最寄りの圃場と紐づけます。

        複数の写真（写真A、写真Bなど）それぞれについて、GPSメタデータから撮影位置を抽出し、
        候補となる圃場リストの中から最も近い圃場を特定します。この処理により、
        各写真がどの圃場を撮影したものかを自動的に判別します。

        Args:
            photo_path_list: 処理する写真ファイルのパスリスト
            land_candidates: 検索対象の圃場リスト（複数の圃場の位置情報）

        Returns:
            list[str]: 処理された写真のパスリスト（圃場と紐づけられた状態）

        Note:
            写真のGPSメタデータから撮影位置を取得し、その位置から最も近い圃場を特定します。
            将来的に写真のリネームや特定フォルダへの移動などの処理も行う予定です。
        """
        processed_photos = []

        # 複数の写真ファイルを処理
        for photo_path in photo_path_list:
            # IMG20230630190442.jpg のようなファイル名になっている
            android_photo = AndroidPhoto(photo_path)
            # 画像（＝撮影位置）から最も近い圃場を特定
            nearest_land = self.find_nearest_land(
                android_photo.location, land_candidates
            )

            # TODO: ここで写真のリネーム処理や output_folder への保存などの操作を行う

            processed_photos.append(photo_path)

        return processed_photos

    def find_nearest_land(
        self, photo_coord: CaptureLocation, land_candidates: LandCandidates
    ) -> LandLocation:
        """撮影位置から最も近い圃場を特定します。

        写真のGPSメタデータから抽出した撮影位置を使用して、候補となる圃場の中から
        最も距離が近い圃場を特定します。カメラの方向情報が含まれている場合は、
        その方向に調整された位置を使用して、より正確に撮影対象の圃場を特定します。

        例えば、複数の隣接する圃場（A1、A2、A3など）を撮影した場合、各写真がどの圃場を
        対象としているかを自動的に判別することができます。

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
        """２つの座標間の距離を計算します。

        xarvioは経度緯度(lng,lat)をエクスポートする一方、
        haversineライブラリは緯度経度(lat,lng)の2セットを受け取って距離を計算します。
        そのため、haversineライブラリを使用する際に座標のタプルを逆にしています。

        Args:
            coord1: 開始座標
            coord2: 終了座標
            unit: 距離の単位（デフォルトはメートル）

        Returns:
            float: 指定単位での2点間の距離
        """
        return haversine(
            coord1.to_google().to_tuple(),
            coord2.to_google().to_tuple(),
            unit=unit,
        )
