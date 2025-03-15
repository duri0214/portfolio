from lib.geo.valueobject.coord import GoogleMapsCoord, XarvioCoord, BaseCoord


class LandLocation(BaseCoord):
    """
    圃場（Land）の位置情報を表すクラス。中心点、境界座標リスト、圃場名を保持します。
    xarvio用に作ったので、(経度,緯度)です。

    Notes:
    xarvioは圃場情報を 経度緯度(lng, lat) のタプルで4以上（通常5）で構成し、その座標をスペースで区切ってエクスポートします。たとえば：
    <coordinates>137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929
    137.6484413,34.7441175 137.6489657,34.7443565</coordinates>
    上記の座標は1つの圃場を表し、最初と最後の座標は同じ位置を示しています（縮小ループ）。

    See Also: https://developers.google.com/kml/documentation/kmlreference?hl=ja#coordinates
    """

    def __init__(self, coord_str: str, name: str):
        """
        座標文字列からLandLocationインスタンスを初期化します。

        Args:
            coord_str: スペース区切りの座標文字列 "経度,緯度 経度,緯度 ..."
            name: 圃場の名前
        """
        # 重複を排除
        coords = list(set(coord_str.split()))

        # 元の座標リストを XarvioCoord として保持
        original_coords = []
        latitude_sum = 0.0
        longitude_sum = 0.0

        for coord in coords:
            lng, lat = coord.split(",")
            lng_float = float(lng)
            lat_float = float(lat)
            # XarvioCoordは(latitude, longitude)の順で引数を取る
            original_coords.append(XarvioCoord(lat_float, lng_float))
            longitude_sum += lng_float
            latitude_sum += lat_float

        num_points = len(coords)
        center_lat = round(latitude_sum / num_points, 7)
        center_lng = round(longitude_sum / num_points, 7)

        # 中心点を XarvioCoord として保持
        # XarvioCoordは(latitude, longitude)の順で引数を取る
        self.center = XarvioCoord(center_lat, center_lng)
        self.original_coords = original_coords
        self.name = name

        # BaseCoordの初期化（latitude, longitude）
        super().__init__(center_lat, center_lng)

    def to_tuple(self) -> tuple[float, float]:
        return self.center.to_tuple()

    def to_str(self) -> str:
        return self.center.to_str()

    def to_google(self) -> GoogleMapsCoord:
        return self.center.to_google()
