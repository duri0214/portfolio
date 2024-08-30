from datetime import date, datetime
from unittest import mock

from django.test import TestCase

from soil_analysis.domain.valueobject.weather.jma import XXXTemperatureData
from soil_analysis.management.commands import fetch_weather_forecast
from soil_analysis.management.commands.fetch_weather_forecast import (
    get_data_and_indexes,
)


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


class TestGetDataAndIndexes(TestCase):
    THREE_DAYS = 0
    TYPE_OVERVIEW = 0

    @mock.patch("requests.get")
    def test_get_data_and_indexes(self, mock_requests_get):
        # Preparing mock data
        target_date = datetime.strptime("2024-08-31", "%Y-%m-%d").date()
        mock_response_data = [
            {  # This corresponds to the THREE_DAYS constant
                "timeSeries": [
                    {
                        "timeDefines": [
                            "2024-08-30T17:00:00+09:00",
                            "2024-08-31T00:00:00+09:00",
                            "2024-09-01T00:00:00+09:00",
                        ],
                        "areas": [{"area": {"name": "南部", "code": "280010"}}],
                    },
                    "dummy POPS",
                    "dummy TEMP",
                ]
            },
            "dummy a week forecast",
        ]

        # Mocking requests.get to return the prepared data
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_requests_get.return_value = mock_response

        url = "http://test.url"  # This url doesn't matter as we mock the requests.get
        data_time_series, indexes = get_data_and_indexes(
            url=url, type_needle=self.TYPE_OVERVIEW, desired_date=target_date
        )

        self.assertEqual(
            mock_response_data[self.THREE_DAYS]["timeSeries"][self.TYPE_OVERVIEW],
            data_time_series,
        )
        self.assertEqual(indexes, [1])
