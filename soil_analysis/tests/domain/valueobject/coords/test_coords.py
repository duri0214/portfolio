from unittest import TestCase

from soil_analysis.domain.valueobject.coords import (
    GoogleMapCoords,
    CaptureLocationCoords,
    LandCoords,
)


class TestCoords(TestCase):
    def test_xarvio_coords_get_coords(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        xarvio_coords = LandCoords(coords_str)
        self.assertEqual((137.6490462, 34.7442398), xarvio_coords.to_tuple())
        self.assertEqual("137.6490462, 34.7442398", xarvio_coords.to_str())

    def test_land_coords_to_googlemap_coords(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        land_coords = LandCoords(coords_str)
        googlemap_coords = land_coords.to_googlemap()
        self.assertEqual((34.7442398, 137.6490462), googlemap_coords.to_tuple())
        self.assertEqual("34.7442398, 137.6490462", googlemap_coords.to_str())

    def test_googlemap_coords_get_coords(self):
        googlemap_coords = GoogleMapCoords(34.7443565, 137.6489657)
        self.assertEqual((34.7443565, 137.6489657), googlemap_coords.to_tuple())
        self.assertEqual("34.7443565, 137.6489657", googlemap_coords.to_str())

    def test_capture_location_coord_get_coords(self):
        capture_location_coords = CaptureLocationCoords(137.6489657, 34.7443565)
        self.assertEqual((34.7443565, 137.6489657), capture_location_coords.to_tuple())
        self.assertEqual("34.7443565, 137.6489657", capture_location_coords.to_str())
