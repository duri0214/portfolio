import math

from lib.geo.valueobject.coord import XarvioCoord


class CaptureLocation:
    """撮影位置と方向を表現し、圃場特定のための位置補正を行うクラス。

    ## 背景と目的

    写真から最も近い圃場を特定する際、撮影位置が複数の圃場から等距離にある場合、
    単純な距離計算では正確な圃場を特定できません。例えば：

    - 圃場A、Bが道路の両側にある
    - 道路の真ん中から写真を撮影した
    - 単純な距離計算では圃場Aと圃場Bの距離が同じになる

    ## 解決アプローチ

    このクラスでは、カメラが向いている方向（方位角）を考慮し、その方向にわずかに
    進んだ位置（デフォルトで10m）を「補正位置」として計算します。

    例：
    1. カメラを圃場Bに向けて撮影
    2. 方位角を使って撮影位置から圃場B方向に10m進んだ位置を計算
    3. この補正位置は圃場Bに近く、圃場Aからは遠くなる
    4. 補正位置を使って最短距離の圃場を計算すると、圃場Bが選ばれる
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
        self._azimuth = azimuth

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

        return XarvioCoord(
            longitude=destination_longitude, latitude=destination_latitude
        )

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

    def __repr__(self):
        """開発者向けの文字列表現を返します。

        Returns:
            str: オブジェクトを再現可能な詳細な表現
        """
        return f"CaptureLocation(longitude={self._original_position.longitude}, latitude={self._original_position.latitude}, azimuth={self._azimuth})"
