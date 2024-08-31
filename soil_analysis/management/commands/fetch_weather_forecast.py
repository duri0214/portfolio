from datetime import datetime, timedelta, date

import requests
from django.core.management import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import (
    WeatherForecast,
    WindData,
    MeanCalculable,
)
from soil_analysis.models import JmaWeather

THREE_DAYS = 0

TYPE_OVERVIEW = 0
TYPE_RAIN = 1
TYPE_TEMPERATURE = 2
TYPE_WIND = 1

WIND_SPEED = 3
LAND = 0


def update_prefecture_ids(jma_prefecture_ids: list[str]) -> list[str]:
    """
    気象庁特別ルール
    "014030" があって "014100" がないときに "014030" → "014100" に置換 / 十勝地方 → 釧路・根室地方
    "460040" があって "460100" がないときに "460040" → "460100" に置換 / 奄美地方 → 鹿児島県（奄美地方除く）

    Args:
        jma_prefecture_ids (list[str]): The list of JMA prefecture IDs.

    Returns:
        list[str]: The updated list of JMA prefecture IDs.
    """
    pairs_to_check = [("014030", "014100"), ("460040", "460100")]

    for invalid_id, proxy_id in pairs_to_check:
        if invalid_id in jma_prefecture_ids:
            if proxy_id not in jma_prefecture_ids:
                jma_prefecture_ids.append(proxy_id)
            jma_prefecture_ids.remove(invalid_id)
    return jma_prefecture_ids


def get_data(url: str):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data[THREE_DAYS]["timeSeries"]


def get_indexes(data_time_defines, desired_date: date) -> list[int]:
    """
    get_indexes する箇所が複数あるので独立さした

    Args:
        data_time_defines: ["2024-08-31", "2024-09-01", "2024-09-01"]
        desired_date: "2024-09-01"

    Returns: [1, 2]
    """
    return [
        i
        for i, date_str in enumerate(data_time_defines)
        if datetime.fromisoformat(date_str).date() == desired_date
    ]


class Command(BaseCommand):
    help = "get weather forecast"

    def handle(self, *args, **options):
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        # TODO: 例えば建物の jma_prefecture_ids をdbから取得（重複を削って）
        jma_prefecture_ids = ["280000", "050000", "130000", "014030", "460040"]
        jma_prefecture_ids = update_prefecture_ids(jma_prefecture_ids)

        if not jma_prefecture_ids:
            raise Exception("facility is empty")

        JmaWeather.objects.all().delete()
        for prefecture_id in jma_prefecture_ids:
            # 風速
            print(f"{prefecture_id=}")
            url = f"https://www.jma.go.jp/bosai/probability/data/probability/{prefecture_id}.json"
            time_series_wind_data = get_data(url)

            # 値の取り出し（TODO: いまは tomorrow の3値のみ。のちほど数日分を取れるようにする）
            indexes = get_indexes(
                data_time_defines=time_series_wind_data[TYPE_WIND]["timeDefines"],
                desired_date=tomorrow,
            )
            for region_data in time_series_wind_data[TYPE_WIND]["areas"]:
                forecasts_by_region = {}
                region_code = region_data["code"]
                time_cells_wind_data = region_data["properties"][WIND_SPEED][
                    "timeCells"
                ]
                wind_data = WindData(
                    values=MeanCalculable(
                        [
                            int(time_cell["locals"][LAND]["value"])
                            for i, time_cell in enumerate(time_cells_wind_data)
                            if i in indexes
                        ]
                    )
                )
                forecasts_by_region.setdefault(region_code, {}).setdefault(
                    "wind_speed", {}
                )[tomorrow] = wind_data

                for region, forecast_data in forecasts_by_region.items():
                    for weather_date, wind_data in forecast_data["wind_speed"].items():
                        print(f"  {region} の {weather_date} の {wind_data}")

            # 天気コード・天気サマリ・風サマリ・波サマリ（いまは tomorrow のみ）
            # url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
            # time_series_overview_data, indexes = get_data_and_indexes(
            #     url=url, desired_date=tomorrow
            # )
            # time_defines = time_series_overview_data[TYPE_OVERVIEW]["timeDefines"]
            # for region_data in time_series_overview_data[TYPE_OVERVIEW]["areas"]:
            #     # Create Region instance
            #     region = Region(
            #         code=region_data["area"]["code"],
            #         name=region_data["area"]["name"],
            #     )
            #     # Create list of Weather instances
            #     weather_data_list: list[WeatherData] = []
            #     for (
            #         time_define,
            #         weather_code,
            #         weather_text,
            #         wind_text,
            #         wave_text,
            #     ) in zip(
            #         time_defines,
            #         region_data["weatherCodes"],
            #         region_data["weathers"],
            #         region_data["winds"],
            #         region_data["waves"],
            #     ):
            #         rain_data = forecasts_time_series[TYPE_RAIN]
            #         temperature_data = forecasts_time_series[TYPE_TEMPERATURE]
            #         weather_data = WeatherData(
            #             time_defined=datetime.fromisoformat(time_define),
            #             code=weather_code,
            #             summary_text=SummaryText(
            #                 weather=weather_text, wind=wind_text, wave=wave_text
            #             ),
            #             rain_data=RainData(),
            #             temperature_data=TemperatureData(),
            #             wind_data=WindData(),
            #         )
            #         weather_data_list.append(weather_data)
            #
            #     # ここまでOK
            #
            #     # その地域にあるアメダスid
            #     amedas_ids = [
            #         amedas.id
            #         for amedas in JmaAmedas.objects.filter(jma_area3_id=region.code)
            #     ]
            #
            # # 降水確率（いまは tomorrow のみ）
            # for region_data in time_series_overview_data[TYPE_RAIN]["areas"]:
            #     continue
            #
            # # 気温（いまは tomorrow のみ）
            # for region_data in time_series_overview_data[TYPE_TEMPERATURE]["areas"]:
            #     continue

            # # 天気・風・波・降水確率・気温 をガッチャンコ
            weather_forecast_list: list[WeatherForecast] = []
            # for region_code, forecast in forecasts_by_region.items():
            #     region_forecast_results = RegionForecastResults(
            #         forecast["weather"],
            #         forecast["temperature"],
            #         forecast["wind_speed"],
            #     )
            #     print(region_forecast_results)
            #     weather_forecast_list.append(region_forecast_results)

            # db登録
            # JmaWeather.objects.bulk_create(
            #     [
            #         JmaWeather(
            #             jma_areas3_id=item.region_weather.region_code,
            #             weather_code=item.region_weather.weather_code,
            #             temperature_min=item.region_temperature.avg_min_temps,
            #             temperature_max=item.region_temperature.avg_max_temps,
            #             wind_speed=item.region_wind_speed.avg_wind_speed,
            #         )
            #         for item in weather_forecast_list
            #     ]
            # )

        self.stdout.write(
            self.style.SUCCESS("weather forecast data retrieve has been completed.")
        )
