from datetime import date

from django.test import TestCase

from soil_analysis.domain.valueobject.weather.jma import XXXTemperatureData
from soil_analysis.management.commands import fetch_weather_forecast


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

        min_temps_idx, max_temps_idx = XXXTemperatureData.get_indexes_from_time_defines(
            time_defines, target_date
        )
        self.assertEqual(min_temps_idx, 1)
        self.assertEqual(max_temps_idx, 2)

    def test_no_indexes_in_time_defines(self):
        time_defines = ["2023-03-16", "2023-03-17", "2023-03-19", "2023-03-20"]
        target_date = date(2023, 3, 18)

        indexes = XXXTemperatureData.get_indexes_from_time_defines(
            time_defines, target_date
        )
        self.assertEqual(indexes, [])


class TestFetchWeatherForecast(TestCase):
    def setUp(self):
        # 天気予報取得バッチの 十勝地方、奄美地方 変換
        self.func = fetch_weather_forecast.update_prefecture_ids

    def test_update_prefecture_ids_with_invalid_id(self):
        jma_prefecture_ids = ["014030", "032010", "082050", "460040"]
        result = self.func(jma_prefecture_ids)

        self.assertListEqual(result, ["032010", "082050", "014100", "460100"])

    def test_update_prefecture_ids_without_invalid_id(self):
        jma_prefecture_ids = ["014100", "032010", "082050", "460100"]
        result = self.func(jma_prefecture_ids)

        self.assertListEqual(result, ["014100", "032010", "082050", "460100"])

    def test_update_prefecture_ids_with_proxy_id(self):
        #  [("014030", "014100"), ("460040", "460100")]
        jma_prefecture_ids = [
            "014030",
            "032010",
            "082050",
            "460040",
            "014100",
            "460100",
        ]
        result = self.func(jma_prefecture_ids)

        self.assertListEqual(result, ["032010", "082050", "014100", "460100"])

    def test_update_prefecture_ids_with_empty_list(self):
        jma_prefecture_ids = []
        result = self.func(jma_prefecture_ids)

        self.assertListEqual(result, [])
