from unittest import TestCase

from lib.geo.valueobject.coords import LandCoords
from soil_analysis.domain.valueobject.land import Land


class TestLand(TestCase):
    def test_land_initialization(self):
        name = "ススムA3"
        coords_str = (
            "137.6492809,34.743865 137.6494646,34.7436029 137.6489644,34.7433683 "
            "137.6487806,34.7436403 137.6492809,34.743865"
        )

        # ススムA3の中心点を google maps で手動で手に入れた
        expected_coords = LandCoords("137.6491060553256,34.74361968398954")

        land = Land(name, coords_str)

        self.assertEqual(name, land.name)
        self.assertAlmostEqual(
            expected_coords.latitude, land.center.latitude, delta=0.0001
        )
        self.assertAlmostEqual(
            expected_coords.longitude, land.center.longitude, delta=0.0001
        )
