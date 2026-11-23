from dataclasses import FrozenInstanceError
from unittest import TestCase

from soil_analysis.domain.service.utm import from_utm, to_utm
from soil_analysis.domain.valueobject.utm import (
    GeographicCoordinate,
    UtmCoordinate,
    UtmZone,
)


class UtmTest(TestCase):
    def test_proj_published_examples(self):
        """シナリオ: 入力: PROJの北半球・南半球の例。処理: 双方向変換。期待値: 公開値と一致しゾーンを保持。"""
        for lon, lat, number, north, east, northing in [
            (12, 56, 32, True, 687071.44, 6210141.33),
            (174, -44, 59, False, 740526.32, 5123750.87),
        ]:
            with self.subTest(zone=number):
                zone = UtmZone(number, north)
                utm = to_utm(GeographicCoordinate(lon, lat), zone)
                self.assertEqual(utm.zone, zone)
                self.assertAlmostEqual(utm.easting, east, delta=0.01)
                self.assertAlmostEqual(utm.northing, northing, delta=0.01)
                result = from_utm(UtmCoordinate(east, northing, zone))
                self.assertAlmostEqual(result.longitude, lon, delta=0.000001)
                self.assertAlmostEqual(result.latitude, lat, delta=0.000001)

    def test_invalid_values_and_hemisphere(self):
        """シナリオ: 入力: 無効な値と異なる半球。処理: 値の作成・変換。期待値: ValueError。"""
        for number, north in [(0, True), (61, True), (True, True), (31, 1)]:
            with self.subTest(number=number, north=north), self.assertRaises(
                ValueError
            ):
                UtmZone(number, north)
        for lon, lat in [(0, 85), (float("nan"), 0), (181, 0)]:
            with self.subTest(lon=lon, lat=lat), self.assertRaises(ValueError):
                GeographicCoordinate(lon, lat)
        with self.assertRaises(ValueError):
            UtmCoordinate(0, 0, UtmZone(31, True))
        with self.assertRaises(ValueError):
            to_utm(GeographicCoordinate(0, -1), UtmZone(31, True))

    def test_value_objects_are_immutable(self):
        """シナリオ: 入力: 座標とゾーンの値。処理: 属性を変更。期待値: 更新を拒否する。"""
        zone = UtmZone(32, True)
        coordinate = UtmCoordinate(500000, 0, zone)
        with self.assertRaises(FrozenInstanceError):
            zone.number = 33
        with self.assertRaises(FrozenInstanceError):
            coordinate.easting = 600000
