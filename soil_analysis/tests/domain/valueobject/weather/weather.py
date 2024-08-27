from datetime import date
from unittest import TestCase

from soil_analysis.domain.valueobject.weather.weather import RegionTemperature


class TestGetIndexFromTimeDefines(TestCase):

    def test_get_indexes_from_time_defines(self):
        time_defines = [
            "2023-03-17T00:00:00+09:00",
            "2023-03-18T00:00:00+09:00",
            "2023-03-18T09:00:00+09:00",
            "2023-03-19T00:00:00+09:00",
            "2023-03-19T09:00:00+09:00",
        ]
        target_date = date(2023, 3, 18)

        min_temps_idx, max_temps_idx = RegionTemperature.get_indexes_from_time_defines(
            time_defines, target_date
        )
        self.assertEqual(min_temps_idx, 1)
        self.assertEqual(max_temps_idx, 2)

    def test_no_indexes_in_time_defines(self):
        time_defines = ["2023-03-16", "2023-03-17", "2023-03-19", "2023-03-20"]
        target_date = date(2023, 3, 18)

        indexes = RegionTemperature.get_indexes_from_time_defines(
            time_defines, target_date
        )
        self.assertEqual(indexes, [])
