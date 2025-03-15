from unittest import TestCase

from soil_analysis.domain.valueobject.land import LandLocation
from soil_analysis.domain.valueobject.landcandidates import LandCandidates


class TestLandCandidates(TestCase):
    def test_add(self):
        candidates = LandCandidates()
        land1 = LandLocation("137.6492809,34.743865", "Land A")
        land2 = LandLocation("137.6487935,34.744671", "Land B")

        candidates.add(land1)
        candidates.add(land2)

        self.assertEqual(len(candidates.list()), 2)

    def test_search_existing_land(self):
        candidates = LandCandidates()
        land1 = LandLocation("137.6492809,34.743865", "Land A")
        land2 = LandLocation("137.6487935,34.744671", "Land B")

        candidates.add(land1)
        candidates.add(land2)

        found_land = candidates.search("Land A")
        self.assertEqual(found_land, land1)

    def test_search_non_existing_land(self):
        candidates = LandCandidates()
        land1 = LandLocation("137.6492809,34.743865", "Land A")
        land2 = LandLocation("137.6487935,34.744671", "Land B")

        candidates.add(land1)
        candidates.add(land2)

        with self.assertRaises(ValueError):
            candidates.search("Land C")

    def test_list(self):
        candidates = LandCandidates()
        land1 = LandLocation("137.6492809,34.743865", "Land A")
        land2 = LandLocation("137.6487935,34.744671", "Land B")

        candidates.add(land1)
        candidates.add(land2)

        land_list = candidates.list()
        self.assertEqual(len(land_list), 2)
        self.assertIn(land1, land_list)
        self.assertIn(land2, land_list)
