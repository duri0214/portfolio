from datetime import datetime, timedelta, date

import requests
from django.core.management import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import (
    WindData,
    MeanCalculable,
    Region,
    SummaryText,
    RainData,
    TemperatureData,
)
from soil_analysis.models import JmaWeather, JmaRegion, JmaPrefecture, JmaAmedas

THREE_DAYS = 0

TYPE_OVERVIEW = 0
TYPE_RAIN = 1
TYPE_TEMPERATURE = 2
TYPE_WIND = 1

WIND_SPEED = 3
LAND = 0


def update_prefecture_ids(prefecture_ids: list[str]) -> tuple[list[str], dict]:
    """
    気象庁特別ルール
    "014030" があって "014100" がないときに "014030" → "014100" に置換 / 十勝地方 → 釧路・根室地方
    "460040" があって "460100" がないときに "460040" → "460100" に置換 / 奄美地方 → 鹿児島県（奄美地方除く）

    Args:
        prefecture_ids (list[str]): The list of JMA prefecture ids to be updated.

    Returns:
        tuple[list[str], dict]: JMA prefecture ids and special add region ids.

    Example:
        prefecture_ids = ["014030", "460040"]
        updated_ids, special_add_region_ids = update_prefecture_ids(prefecture_ids)
        print(updated_ids)  # Output: ["014100", "460100"]
        print(special_add_region_ids)  # Output: {"014100": "014030", "460100": "460040"}
    """
    pairs_to_check = [("014030", "014100"), ("460040", "460100")]
    special_add_region_ids = {}

    for invalid_id, proxy_id in pairs_to_check:
        if invalid_id in prefecture_ids:
            if proxy_id not in prefecture_ids:
                prefecture_ids.append(proxy_id)
            prefecture_ids.remove(invalid_id)
            special_add_region_ids[proxy_id] = invalid_id
    return prefecture_ids, special_add_region_ids


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
        forecasts_by_region = {}

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        forecasts_by_region.setdefault(tomorrow, {})

        # TODO: 例えば建物の jma_prefecture_ids をdbから取得（重複を削って）
        jma_prefecture_ids = ["280000", "050000", "130000", "014030", "460040"]
        jma_prefecture_ids, special_add_region_ids = update_prefecture_ids(
            jma_prefecture_ids
        )

        if not jma_prefecture_ids:
            raise Exception("facility is empty")

        JmaWeather.objects.all().delete()
        for prefecture_id in jma_prefecture_ids:
            print(f"{prefecture_id=} の {tomorrow}")

            # 風速
            print("  風速:")
            url = f"https://www.jma.go.jp/bosai/probability/data/probability/{prefecture_id}.json"
            time_series_data = get_data(url)

            # 値の取り出し（TODO: いまは tomorrow の3値のみ。のちほど数日分を取れるようにする）
            indexes = get_indexes(
                data_time_defines=time_series_data[TYPE_WIND]["timeDefines"],
                desired_date=tomorrow,
            )
            for region_data in time_series_data[TYPE_WIND]["areas"]:
                region_code = region_data["code"]
                forecasts_by_region[tomorrow].setdefault(region_code, {})
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
                forecasts_by_region[tomorrow][region_code]["wind_data"] = wind_data
                print(f"    {region_code} の {wind_data}")

            # 天気コード・天気サマリ・風サマリ・波サマリ（いまは tomorrow のみ）
            print("  天気サマリ:")
            url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{prefecture_id}.json"
            time_series_data = get_data(url)

            # 値の取り出し（TODO: いまは tomorrow の1値のみ。のちほど数日分を取れるようにする）
            indexes = get_indexes(
                data_time_defines=time_series_data[TYPE_OVERVIEW]["timeDefines"],
                desired_date=tomorrow,
            )
            if len(indexes) != 1:
                print(f"    要素数は必ず1になります{len(indexes)}")
                continue
            index = indexes.pop()
            for region_data in time_series_data[TYPE_OVERVIEW]["areas"]:
                region = Region(
                    code=region_data["area"]["code"],
                    name=region_data["area"]["name"],
                )
                forecasts_by_region[tomorrow].setdefault(region.code, {})

                # weather_code
                forecasts_by_region[tomorrow][region.code]["weather_code"] = (
                    region_data["weatherCodes"][index]
                )

                # summary_text を3種
                summary_text = SummaryText(
                    weather=(
                        region_data["weathers"][index]
                        if "weathers" in region_data
                        and index < len(region_data["weathers"])
                        else "なし"
                    ),
                    wind=(
                        region_data["winds"][index]
                        if "winds" in region_data and index < len(region_data["winds"])
                        else "なし"
                    ),
                    wave=(
                        region_data["waves"][index]
                        if "waves" in region_data and index < len(region_data["waves"])
                        else "なし"
                    ),
                )
                forecasts_by_region[tomorrow][region.code][
                    "summary_text"
                ] = summary_text
                print(
                    f"    {region.code} の｜{summary_text.weather[:4]}｜{summary_text.wind[:4]}｜{summary_text.wave[:4]}｜"
                )
                # ここまでOK

            # 降水確率（いまは tomorrow のみ）
            print("  降水確率:")
            # 値の取り出し（TODO: いまは tomorrow の1値のみ。のちほど数日分を取れるようにする）
            indexes = get_indexes(
                data_time_defines=time_series_data[TYPE_RAIN]["timeDefines"],
                desired_date=tomorrow,
            )
            for region_data in time_series_data[TYPE_RAIN]["areas"]:
                region = Region(
                    code=region_data["area"]["code"],
                    name=region_data["area"]["name"],
                )
                forecasts_by_region[tomorrow].setdefault(region.code, {})
                rain_data = RainData(
                    values=MeanCalculable(
                        [
                            int(time_cell)
                            for i, time_cell in enumerate(region_data["pops"])
                            if i in indexes
                        ]
                    )
                )
                forecasts_by_region[tomorrow][region.code]["rain_data"] = rain_data
                print(f"    {region.code} の {rain_data.values.mean} {rain_data.unit}")

            # TODO: repositoryがよさそう {'280010': ['63518', '63576', '63571', '63383'], '280020': ['63051']}
            # その地域にあるアメダスcode
            amedas_code_in_region = {}
            jma_regions = JmaRegion.objects.filter(
                jma_prefecture=JmaPrefecture.objects.get(code=prefecture_id)
            ).prefetch_related("jmaamedas_set")
            for region in jma_regions:
                amedas_code_in_region[region.code] = [
                    amedas.code for amedas in region.jmaamedas_set.all()
                ]
            if prefecture_id in special_add_region_ids:
                region = JmaRegion.objects.get(
                    code=special_add_region_ids[prefecture_id]
                )
                special_add_region_code = special_add_region_ids[prefecture_id]
                amedas_code_in_region[special_add_region_code] = list(
                    JmaAmedas.objects.filter(jma_region=region).values_list(
                        "code", flat=True
                    )
                )

            # 気温（いまは tomorrow のみ） ※気温にはregionの概念がありません
            print("  気温:")
            # 値の取り出し（TODO: いまは tomorrow の1値のみ。のちほど数日分を取れるようにする）
            for region_data in time_series_data[TYPE_OVERVIEW]["areas"]:
                region = Region(
                    code=region_data["area"]["code"],
                    name=region_data["area"]["name"],
                )
                forecasts_by_region[tomorrow].setdefault(region.code, {})

                amedas_min_temps: list[float] = []
                amedas_max_temps: list[float] = []
                for amedas_data in time_series_data[TYPE_TEMPERATURE]["areas"]:
                    amedas_code = amedas_data["area"]["code"]
                    if amedas_code not in amedas_code_in_region.get(region.code):
                        continue
                    amedas_min_temps.append(float(amedas_data["temps"][0]))
                    amedas_max_temps.append(float(amedas_data["temps"][1]))
                forecasts_by_region[tomorrow].setdefault(region.code, {})
                temperature_data = TemperatureData(
                    min_values=MeanCalculable(amedas_min_temps),
                    max_values=MeanCalculable(amedas_max_temps),
                )
                forecasts_by_region[tomorrow][region.code][
                    "temperature_data"
                ] = temperature_data
                msg1 = f"    {region.code} の最低気温 {temperature_data.min_values.mean} {temperature_data.unit}"
                msg2 = f"最高気温 {temperature_data.max_values.mean} {temperature_data.unit}"
                print(f"{msg1} / {msg2}")

            # 天気・風・波・降水確率・気温 をガッチャンコ
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
