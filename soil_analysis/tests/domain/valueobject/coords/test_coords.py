from unittest import TestCase

from soil_analysis.domain.valueobject.coords.capturelocationcoords import (
    CaptureLocationCoords,
)
from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords
from soil_analysis.domain.valueobject.coords.landcoords import LandCoords


class TestCoords(TestCase):
    def test_xarvio_coords_get_coords(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        xarvio_coords = LandCoords(coords_str)
        self.assertEqual((137.6490462, 34.7442398), xarvio_coords.get_coords())
        self.assertEqual(
            "137.6490462, 34.7442398", xarvio_coords.get_coords(to_str=True)
        )

    def test_land_coords_to_googlemap_coords(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        land_coords = LandCoords(coords_str)
        googlemap_coords = land_coords.to_googlemapcoords()
        self.assertEqual((34.7442398, 137.6490462), googlemap_coords.get_coords())
        self.assertEqual(
            "34.7442398, 137.6490462", googlemap_coords.get_coords(to_str=True)
        )

    def test_googlemap_coords_get_coords(self):
        googlemap_coords = GoogleMapCoords(34.7443565, 137.6489657)
        self.assertEqual((34.7443565, 137.6489657), googlemap_coords.get_coords())
        self.assertEqual(
            "34.7443565, 137.6489657", googlemap_coords.get_coords(to_str=True)
        )

    def test_capture_location_coord_get_coords(self):
        capture_location_coords = CaptureLocationCoords(34.7443565, 137.6489657)
        self.assertEqual(
            (34.7443565, 137.6489657), capture_location_coords.get_coords()
        )
        self.assertEqual(
            "34.7443565, 137.6489657", capture_location_coords.get_coords(to_str=True)
        )
