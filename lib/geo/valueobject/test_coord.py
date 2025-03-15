from unittest import TestCase

from lib.geo.valueobject.coord import (
    GoogleMapsCoord,
    CaptureLocationCoords,
    LandCoords,
)


class TestCoords(TestCase):
    def test_xarvio_coords_get_coords(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        xarvio_coords = LandCoords(coords_str)
        self.assertEqual((137.6490462, 34.7442398), xarvio_coords.to_tuple())
        self.assertEqual("137.6490462,34.7442398", xarvio_coords.to_str())

    def test_land_coords_to_google_coord(self):
        coords_str = "137.6489657,34.7443565 137.6491266,34.744123"
        land_coords = LandCoords(coords_str)
        google_coord = land_coords.to_google()
        self.assertEqual((34.7442398, 137.6490462), google_coord.to_tuple())
        self.assertEqual("34.7442398,137.6490462", google_coord.to_str())

    def test_google_coord_get_coords(self):
        google_coord = GoogleMapsCoord(34.7443565, 137.6489657)
        self.assertEqual((34.7443565, 137.6489657), google_coord.to_tuple())
        self.assertEqual("34.7443565,137.6489657", google_coord.to_str())

    def test_capture_location_coord_get_coords(self):
        capture_location_coords = CaptureLocationCoords(137.6489657, 34.7443565)
        self.assertEqual((34.7443565, 137.6489657), capture_location_coords.to_tuple())
        self.assertEqual("34.7443565,137.6489657", capture_location_coords.to_str())
