from unittest import TestCase

from lib.geo.valueobject.coord import XarvioCoord


class TestCoord(TestCase):
    def test_land_coord(self):
        xarvio_coord = XarvioCoord(137.6489657, 34.7443565)
        self.assertEqual((34.7443565, 137.6489657), xarvio_coord.to_tuple())
        self.assertEqual("34.7443565,137.6489657", xarvio_coord.to_str())

        google_coord = xarvio_coord.to_google()
        self.assertEqual((137.6489657, 34.7443565), google_coord.to_tuple())
        self.assertEqual("137.6489657,34.7443565", google_coord.to_str())
