import math

from lib.geo.valueobject.coord import XarvioCoord


class CaptureLocation:
    """
    撮影位置と方向を表現するクラス。

    撮影位置が複数の圃場から等距離にある場合、カメラが向いている方向（方位角）に
    わずかに進んだ位置を考慮することで、撮影位置から一番近い圃場をより正確に特定します。

    Note: 右に圃場１、左に圃場2がある状態で、それら圃場を手前から、かつ圃場の左右の真ん中から撮影したとき、撮影座標との距離の関係性は二等辺三角形になる
      それでは圃場が特定できないので、撮影した方位角（例えば圃場２）に向かって撮影座標を10m補正できれば、圃場１からは少し遠くなり、圃場２へは少し近くなる
      そんな下準備をして find_nearest_land で処理できれば、写真から圃場を特定できる
    """

    # クラス定数
    ADJUSTMENT_DISTANCE_KM = 0.01  # 10メートル

    def __init__(self, longitude: float, latitude: float, azimuth: float = None):
        """CaptureLocation オブジェクトを初期化します。

        Args:
            longitude: 経度
            latitude: 緯度
            azimuth: 方位角（度）。指定された場合、この方向に少し移動した位置も計算します。
        """
        self._original_position = XarvioCoord(
            longitude=longitude,
            latitude=latitude,
        )

        if azimuth:
            self._adjusted_position = self._calculate_adjusted_position(azimuth)
        else:
            self._adjusted_position = self._original_position

    def _calculate_adjusted_position(
        self, azimuth: float, distance: float = ADJUSTMENT_DISTANCE_KM
    ):
        """指定された方位角と距離に基づいて、調整された位置座標を計算します。

        デフォルトでは方位角の方向に10mの距離を進んだ位置を計算します。

        Args:
            azimuth: 方位角（単位: 度）
            distance: 移動距離（単位: キロメートル、デフォルト0.01km = 10m）

        Returns:
            XarvioCoord: 調整後の座標
        """
        origin_longitude, origin_latitude = self._original_position.to_tuple()

        # 角度をラジアンに変換
        azimuth_rad = math.radians(azimuth)
        # 緯度をラジアンに変換
        latitude_rad = math.radians(origin_latitude)
        # 赤道半径（地球の半径）を設定
        radius = 6371.0  # 地球の半径（キロメートル）

        # 目的地までの変位の緯度変化を計算
        delta_latitude = distance / radius * math.cos(azimuth_rad)
        # 目的地までの変位の経度変化を計算
        delta_longitude = (
            distance / (radius * math.sin(latitude_rad)) * math.sin(azimuth_rad)
        )

        # 目的地の緯度を計算
        destination_latitude = origin_latitude + math.degrees(delta_latitude)
        # 目的地の経度を計算
        destination_longitude = origin_longitude + math.degrees(delta_longitude)

        return XarvioCoord(destination_longitude, destination_latitude)

    @property
    def adjusted_position(self) -> XarvioCoord:
        """カメラの方位角方向に10m進んだ調整後の位置を取得します。

        Returns:
            XarvioCoord: 調整後の位置座標
        """
        return self._adjusted_position

    @property
    def original_position(self) -> XarvioCoord:
        """実際の撮影位置を取得します。

        Returns:
            XarvioCoord: 元の撮影位置座標
        """
        return self._original_position
