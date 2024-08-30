from datetime import datetime, timedelta, date

import requests
from django.core.management import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import (
    Region,
    WeatherForecast,
    WeatherData,
    SummaryText,
    RainData,
    TemperatureData,
    WindData,
)
from soil_analysis.models import JmaWeather, JmaAmedas

THREE_DAYS = 0

TYPE_OVERVIEW = 0
TYPE_RAIN = 1
TYPE_TEMPERATURE = 2
TYPE_WIND = 1

MAX_WIND_SPEED = 3
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


def get_data_and_indexes(url: str, type_needle: int, desired_date: date):
    response = requests.get(url)
    response.raise_for_status()

    data = response.json()
    data_time_series = data[THREE_DAYS]["timeSeries"][type_needle]
    indexes = [
        i
        for i, date_str in enumerate(data_time_series["timeDefines"])
        if datetime.fromisoformat(date_str).date() == desired_date
    ]

    return data_time_series, indexes


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
            # 風速 TODO: 先に風速を処理して3日分のwind[]を作ってしまおう
            response = requests.get(
                f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as err:
                print(f"Error: {err}")
                continue
            probabilities = response.json()
            probabilities_time_series = probabilities[THREE_DAYS]["timeSeries"]
            # TODO: 位置出しはクラスのなかにしまい込めないか？最大風速は１日分４要素なので [1, 2, 3, 4]
            tomorrow_indexes = [
                i
                for i, date_str in enumerate(
                    probabilities_time_series[TYPE_WIND]["timeDefines"]
                )
                if datetime.fromisoformat(date_str).date() == tomorrow
            ]

            # 風速
            print(LAND)  # LANDが消えないように
            # TODO: 消す（明日の風速を辞書にセット）
            # for region_data in probabilities[0]["timeSeries"][1]["areas"]:
            #     time_cells = region_data["properties"][MAX_SPEED]["timeCells"]
            #
            #     # 明日の風速値だけを抽出
            #     wind_values = [
            # int(time_cell["locals"][LAND]["value"])
            #         for i, time_cell in enumerate(time_cells)
            #         if i in tomorrow_indexes
            #     ]
            #     avg_wind_speed = round(sum(wind_values) / len(wind_values), 1)
            #     print(f"{region_data["code"]} の最大風速（日中平均）は {avg_wind_speed}")
            #
            # forecasts_by_region = {
            #     "wind_speed": RegionWindSpeed(
            #         region_code="300", data={}, target_indexes=[1, 2, 3, 4]
            #     )
            # }
            #

            # 天気・波・降水確率・気温（日付ごとに）
            response = requests.get(
                f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as err:
                print(f"Error: {err}")
                continue
            forecasts = response.json()
            forecasts_time_series = forecasts[THREE_DAYS]["timeSeries"]
            # TODO: 位置出しはクラスのなかにしまい込めないか？
            tomorrow_index = None
            for i, date_str in enumerate(
                forecasts_time_series[TYPE_OVERVIEW]["timeDefines"]
            ):
                if datetime.fromisoformat(date_str).date() == tomorrow:
                    tomorrow_index = i
                    break

            overview = forecasts_time_series[TYPE_OVERVIEW]
            for region_data in overview["areas"]:
                # Create Region instance
                region = Region(
                    code=region_data["area"]["code"],
                    name=region_data["area"]["name"],
                )
                # Create list of Weather instances
                weather_data_list: list[WeatherData] = []
                for (
                    time_define,
                    weather_code,
                    weather_text,
                    wind_text,
                    wave_text,
                ) in zip(
                    overview["timeDefines"],
                    region_data["weatherCodes"],
                    region_data["weathers"],
                    region_data["winds"],
                    region_data["waves"],
                ):
                    rain_data = forecasts_time_series[TYPE_RAIN]
                    temperature_data = forecasts_time_series[TYPE_TEMPERATURE]
                    weather_data = WeatherData(
                        time_defined=datetime.fromisoformat(time_define),
                        code=weather_code,
                        summary_text=SummaryText(
                            weather=weather_text, wind=wind_text, wave=wave_text
                        ),
                        rain_data=RainData(),
                        temperature_data=TemperatureData(),
                        wind_data=WindData(),
                    )
                    weather_data_list.append(weather_data)

                # ここまでOK

                # その地域にあるアメダスid
                amedas_ids = [
                    amedas.id
                    for amedas in JmaAmedas.objects.filter(jma_area3_id=region.code)
                ]

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
