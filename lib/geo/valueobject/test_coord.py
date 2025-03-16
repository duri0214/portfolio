from unittest import TestCase

from lib.geo.valueobject.coord import XarvioCoord, GoogleMapsCoord


class TestCoord(TestCase):
    def test_land_coord(self):
        """座標クラスの変換機能をテストします。

        XarvioCoord (経度,緯度) と GoogleMapsCoord (緯度,経度) の
        相互変換と文字列表現をテストします。
        """
        xarvio_coord = XarvioCoord(34.7443565, 137.6489657)
        self.assertEqual((137.6489657, 34.7443565), xarvio_coord.to_tuple())
        self.assertEqual("137.6489657,34.7443565", xarvio_coord.to_str())

        google_coord = GoogleMapsCoord(34.7443565, 137.6489657)
        self.assertEqual((34.7443565, 137.6489657), google_coord.to_tuple())
        self.assertEqual("34.7443565,137.6489657", google_coord.to_str())
