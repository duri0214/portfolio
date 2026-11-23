from unittest import TestCase

from soil_analysis.domain.service.utm import from_utm, to_utm


class UtmTest(TestCase):
    def test_proj_published_examples(self):
        """シナリオ: 入力: PROJの北半球・南半球の例。処理: 双方向変換。期待値: 公開値と一致。"""
        for lon, lat, zone, north, east, northing in [
            (12, 56, 32, True, 687071.44, 6210141.33),
            (174, -44, 59, False, 740526.32, 5123750.87),
        ]:
            with self.subTest(zone=zone):
                x, y = to_utm(lon, lat, zone, north)
                self.assertAlmostEqual(x, east, delta=0.01)
                self.assertAlmostEqual(y, northing, delta=0.01)
                actual_lon, actual_lat = from_utm(east, northing, zone, north)
                self.assertAlmostEqual(actual_lon, lon, delta=0.000001)
                self.assertAlmostEqual(actual_lat, lat, delta=0.000001)

    def test_invalid_input(self):
        """シナリオ: 入力: 無効な座標、ゾーン、半球。処理: 変換。期待値: ValueError。"""
        for args in [
            (0, 0, 0, True),
            (0, 85, 31, True),
            (0, -1, 31, True),
            (float("nan"), 0, 31, True),
            (0, 0, 31, 1),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                to_utm(*args)
        with self.assertRaises(ValueError):
            from_utm(0, 0, 31, True)
