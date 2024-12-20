import os
import shutil

import requests
from django.core.management.base import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import JmaConstWeatherCode
from soil_analysis.models import (
    JmaWeatherCode,
)


class Command(BaseCommand):
    help = "Import jma weather code master from manual data."

    def handle(self, *args, **options):
        """
        任意の都市の天気ページの `ページのソースを表示` から `TELOPS=` でページ内検索して data に当て込む
        https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=2810000

        Args:
            *args: Additional positional arguments.
            **options: Additional keyword arguments.
        """
        data = {
            100: ["100.svg", "500.svg", "100", "\u6674", "CLEAR"],
            101: [
                "101.svg",
                "501.svg",
                "100",
                "\u6674\u6642\u3005\u66C7",
                "PARTLY CLOUDY",
            ],
            102: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u4E00\u6642\u96E8",
                "CLEAR, OCCASIONAL SCATTERED SHOWERS",
            ],
            103: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u6642\u3005\u96E8",
                "CLEAR, FREQUENT SCATTERED SHOWERS",
            ],
            104: [
                "104.svg",
                "504.svg",
                "400",
                "\u6674\u4E00\u6642\u96EA",
                "CLEAR, SNOW FLURRIES",
            ],
            105: [
                "104.svg",
                "504.svg",
                "400",
                "\u6674\u6642\u3005\u96EA",
                "CLEAR, FREQUENT SNOW FLURRIES",
            ],
            106: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u4E00\u6642\u96E8\u304B\u96EA",
                "CLEAR, OCCASIONAL SCATTERED SHOWERS OR SNOW FLURRIES",
            ],
            107: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u6642\u3005\u96E8\u304B\u96EA",
                "CLEAR, FREQUENT SCATTERED SHOWERS OR SNOW FLURRIES",
            ],
            108: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u4E00\u6642\u96E8\u304B\u96F7\u96E8",
                "CLEAR, OCCASIONAL SCATTERED SHOWERS AND/OR THUNDER",
            ],
            110: [
                "110.svg",
                "510.svg",
                "100",
                "\u6674\u5F8C\u6642\u3005\u66C7",
                "CLEAR, PARTLY CLOUDY LATER",
            ],
            111: [
                "110.svg",
                "510.svg",
                "100",
                "\u6674\u5F8C\u66C7",
                "CLEAR, CLOUDY LATER",
            ],
            112: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5F8C\u4E00\u6642\u96E8",
                "CLEAR, OCCASIONAL SCATTERED SHOWERS LATER",
            ],
            113: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5F8C\u6642\u3005\u96E8",
                "CLEAR, FREQUENT SCATTERED SHOWERS LATER",
            ],
            114: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5F8C\u96E8",
                "CLEAR,RAIN LATER",
            ],
            115: [
                "115.svg",
                "515.svg",
                "400",
                "\u6674\u5F8C\u4E00\u6642\u96EA",
                "CLEAR, OCCASIONAL SNOW FLURRIES LATER",
            ],
            116: [
                "115.svg",
                "515.svg",
                "400",
                "\u6674\u5F8C\u6642\u3005\u96EA",
                "CLEAR, FREQUENT SNOW FLURRIES LATER",
            ],
            117: [
                "115.svg",
                "515.svg",
                "400",
                "\u6674\u5F8C\u96EA",
                "CLEAR,SNOW LATER",
            ],
            118: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5F8C\u96E8\u304B\u96EA",
                "CLEAR, RAIN OR SNOW LATER",
            ],
            119: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5F8C\u96E8\u304B\u96F7\u96E8",
                "CLEAR, RAIN AND/OR THUNDER LATER",
            ],
            120: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u671D\u5915\u4E00\u6642\u96E8",
                "OCCASIONAL SCATTERED SHOWERS IN THE MORNING AND EVENING, CLEAR DURING THE DAY",
            ],
            121: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u671D\u306E\u5185\u4E00\u6642\u96E8",
                "OCCASIONAL SCATTERED SHOWERS IN THE MORNING, CLEAR DURING THE DAY",
            ],
            122: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5915\u65B9\u4E00\u6642\u96E8",
                "CLEAR, OCCASIONAL SCATTERED SHOWERS IN THE EVENING",
            ],
            123: [
                "100.svg",
                "500.svg",
                "100",
                "\u6674\u5C71\u6CBF\u3044\u96F7\u96E8",
                "CLEAR IN THE PLAINS, RAIN AND THUNDER NEAR MOUTAINOUS AREAS",
            ],
            124: [
                "100.svg",
                "500.svg",
                "100",
                "\u6674\u5C71\u6CBF\u3044\u96EA",
                "CLEAR IN THE PLAINS, SNOW NEAR MOUTAINOUS AREAS",
            ],
            125: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5348\u5F8C\u306F\u96F7\u96E8",
                "CLEAR, RAIN AND THUNDER IN THE AFTERNOON",
            ],
            126: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u663C\u9803\u304B\u3089\u96E8",
                "CLEAR, RAIN IN THE AFTERNOON",
            ],
            127: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u5915\u65B9\u304B\u3089\u96E8",
                "CLEAR, RAIN IN THE EVENING",
            ],
            128: [
                "112.svg",
                "512.svg",
                "300",
                "\u6674\u591C\u306F\u96E8",
                "CLEAR, RAIN IN THE NIGHT",
            ],
            130: [
                "100.svg",
                "500.svg",
                "100",
                "\u671D\u306E\u5185\u9727\u5F8C\u6674",
                "FOG IN THE MORNING, CLEAR LATER",
            ],
            131: [
                "100.svg",
                "500.svg",
                "100",
                "\u6674\u660E\u3051\u65B9\u9727",
                "FOG AROUND DAWN, CLEAR LATER",
            ],
            132: [
                "101.svg",
                "501.svg",
                "100",
                "\u6674\u671D\u5915\u66C7",
                "CLOUDY IN THE MORNING AND EVENING, CLEAR DURING THE DAY",
            ],
            140: [
                "102.svg",
                "502.svg",
                "300",
                "\u6674\u6642\u3005\u96E8\u3067\u96F7\u3092\u4F34\u3046",
                "CLEAR, FREQUENT SCATTERED SHOWERS AND THUNDER",
            ],
            160: [
                "104.svg",
                "504.svg",
                "400",
                "\u6674\u4E00\u6642\u96EA\u304B\u96E8",
                "CLEAR, SNOW FLURRIES OR OCCASIONAL SCATTERED SHOWERS",
            ],
            170: [
                "104.svg",
                "504.svg",
                "400",
                "\u6674\u6642\u3005\u96EA\u304B\u96E8",
                "CLEAR, FREQUENT SNOW FLURRIES OR SCATTERED SHOWERS",
            ],
            181: [
                "115.svg",
                "515.svg",
                "400",
                "\u6674\u5F8C\u96EA\u304B\u96E8",
                "CLEAR, SNOW OR RAIN LATER",
            ],
            200: ["200.svg", "200.svg", "200", "\u66C7", "CLOUDY"],
            201: [
                "201.svg",
                "601.svg",
                "200",
                "\u66C7\u6642\u3005\u6674",
                "MOSTLY CLOUDY",
            ],
            202: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u4E00\u6642\u96E8",
                "CLOUDY, OCCASIONAL SCATTERED SHOWERS",
            ],
            203: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u6642\u3005\u96E8",
                "CLOUDY, FREQUENT SCATTERED SHOWERS",
            ],
            204: [
                "204.svg",
                "204.svg",
                "400",
                "\u66C7\u4E00\u6642\u96EA",
                "CLOUDY, OCCASIONAL SNOW FLURRIES",
            ],
            205: [
                "204.svg",
                "204.svg",
                "400",
                "\u66C7\u6642\u3005\u96EA",
                "CLOUDY FREQUENT SNOW FLURRIES",
            ],
            206: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u4E00\u6642\u96E8\u304B\u96EA",
                "CLOUDY, OCCASIONAL SCATTERED SHOWERS OR SNOW FLURRIES",
            ],
            207: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u6642\u3005\u96E8\u304B\u96EA",
                "CLOUDY, FREQUENT SCCATERED SHOWERS OR SNOW FLURRIES",
            ],
            208: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u4E00\u6642\u96E8\u304B\u96F7\u96E8",
                "CLOUDY, OCCASIONAL SCATTERED SHOWERS AND/OR THUNDER",
            ],
            209: ["200.svg", "200.svg", "200", "\u9727", "FOG"],
            210: [
                "210.svg",
                "610.svg",
                "200",
                "\u66C7\u5F8C\u6642\u3005\u6674",
                "CLOUDY, PARTLY CLOUDY LATER",
            ],
            211: [
                "210.svg",
                "610.svg",
                "200",
                "\u66C7\u5F8C\u6674",
                "CLOUDY, CLEAR LATER",
            ],
            212: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5F8C\u4E00\u6642\u96E8",
                "CLOUDY, OCCASIONAL SCATTERED SHOWERS LATER",
            ],
            213: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5F8C\u6642\u3005\u96E8",
                "CLOUDY, FREQUENT SCATTERED SHOWERS LATER",
            ],
            214: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5F8C\u96E8",
                "CLOUDY, RAIN LATER",
            ],
            215: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u5F8C\u4E00\u6642\u96EA",
                "CLOUDY, SNOW FLURRIES LATER",
            ],
            216: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u5F8C\u6642\u3005\u96EA",
                "CLOUDY, FREQUENT SNOW FLURRIES LATER",
            ],
            217: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u5F8C\u96EA",
                "CLOUDY, SNOW LATER",
            ],
            218: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5F8C\u96E8\u304B\u96EA",
                "CLOUDY, RAIN OR SNOW LATER",
            ],
            219: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5F8C\u96E8\u304B\u96F7\u96E8",
                "CLOUDY, RAIN AND/OR THUNDER LATER",
            ],
            220: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u671D\u5915\u4E00\u6642\u96E8",
                "OCCASIONAL SCCATERED SHOWERS IN THE MORNING AND EVENING, CLOUDY DURING THE DAY",
            ],
            221: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u671D\u306E\u5185\u4E00\u6642\u96E8",
                "CLOUDY OCCASIONAL SCCATERED SHOWERS IN THE MORNING",
            ],
            222: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5915\u65B9\u4E00\u6642\u96E8",
                "CLOUDY, OCCASIONAL SCCATERED SHOWERS IN THE EVENING",
            ],
            223: [
                "201.svg",
                "601.svg",
                "200",
                "\u66C7\u65E5\u4E2D\u6642\u3005\u6674",
                "CLOUDY IN THE MORNING AND EVENING, PARTLY CLOUDY DURING THE DAY,",
            ],
            224: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u663C\u9803\u304B\u3089\u96E8",
                "CLOUDY, RAIN IN THE AFTERNOON",
            ],
            225: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u5915\u65B9\u304B\u3089\u96E8",
                "CLOUDY, RAIN IN THE EVENING",
            ],
            226: [
                "212.svg",
                "212.svg",
                "300",
                "\u66C7\u591C\u306F\u96E8",
                "CLOUDY, RAIN IN THE NIGHT",
            ],
            228: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u663C\u9803\u304B\u3089\u96EA",
                "CLOUDY, SNOW IN THE AFTERNOON",
            ],
            229: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u5915\u65B9\u304B\u3089\u96EA",
                "CLOUDY, SNOW IN THE EVENING",
            ],
            230: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u591C\u306F\u96EA",
                "CLOUDY, SNOW IN THE NIGHT",
            ],
            231: [
                "200.svg",
                "200.svg",
                "200",
                "\u66C7\u6D77\u4E0A\u6D77\u5CB8\u306F\u9727\u304B\u9727\u96E8",
                "CLOUDY, FOG OR DRIZZLING ON THE SEA AND NEAR SEASHORE",
            ],
            240: [
                "202.svg",
                "202.svg",
                "300",
                "\u66C7\u6642\u3005\u96E8\u3067\u96F7\u3092\u4F34\u3046",
                "CLOUDY, FREQUENT SCCATERED SHOWERS AND THUNDER",
            ],
            250: [
                "204.svg",
                "204.svg",
                "400",
                "\u66C7\u6642\u3005\u96EA\u3067\u96F7\u3092\u4F34\u3046",
                "CLOUDY, FREQUENT SNOW AND THUNDER",
            ],
            260: [
                "204.svg",
                "204.svg",
                "400",
                "\u66C7\u4E00\u6642\u96EA\u304B\u96E8",
                "CLOUDY, SNOW FLURRIES OR OCCASIONAL SCATTERED SHOWERS",
            ],
            270: [
                "204.svg",
                "204.svg",
                "400",
                "\u66C7\u6642\u3005\u96EA\u304B\u96E8",
                "CLOUDY, FREQUENT SNOW FLURRIES OR SCATTERED SHOWERS",
            ],
            281: [
                "215.svg",
                "215.svg",
                "400",
                "\u66C7\u5F8C\u96EA\u304B\u96E8",
                "CLOUDY, SNOW OR RAIN LATER",
            ],
            300: ["300.svg", "300.svg", "300", "\u96E8", "RAIN"],
            301: [
                "301.svg",
                "701.svg",
                "300",
                "\u96E8\u6642\u3005\u6674",
                "RAIN, PARTLY CLOUDY",
            ],
            302: [
                "302.svg",
                "302.svg",
                "300",
                "\u96E8\u6642\u3005\u6B62\u3080",
                "SHOWERS THROUGHOUT THE DAY",
            ],
            303: [
                "303.svg",
                "303.svg",
                "400",
                "\u96E8\u6642\u3005\u96EA",
                "RAIN,FREQUENT SNOW FLURRIES",
            ],
            304: ["300.svg", "300.svg", "300", "\u96E8\u304B\u96EA", "RAINORSNOW"],
            306: ["300.svg", "300.svg", "300", "\u5927\u96E8", "HEAVYRAIN"],
            308: [
                "308.svg",
                "308.svg",
                "300",
                "\u96E8\u3067\u66B4\u98A8\u3092\u4F34\u3046",
                "RAINSTORM",
            ],
            309: [
                "303.svg",
                "303.svg",
                "400",
                "\u96E8\u4E00\u6642\u96EA",
                "RAIN,OCCASIONAL SNOW",
            ],
            311: [
                "311.svg",
                "711.svg",
                "300",
                "\u96E8\u5F8C\u6674",
                "RAIN,CLEAR LATER",
            ],
            313: [
                "313.svg",
                "313.svg",
                "300",
                "\u96E8\u5F8C\u66C7",
                "RAIN,CLOUDY LATER",
            ],
            314: [
                "314.svg",
                "314.svg",
                "400",
                "\u96E8\u5F8C\u6642\u3005\u96EA",
                "RAIN, FREQUENT SNOW FLURRIES LATER",
            ],
            315: ["314.svg", "314.svg", "400", "\u96E8\u5F8C\u96EA", "RAIN,SNOW LATER"],
            316: [
                "311.svg",
                "711.svg",
                "300",
                "\u96E8\u304B\u96EA\u5F8C\u6674",
                "RAIN OR SNOW, CLEAR LATER",
            ],
            317: [
                "313.svg",
                "313.svg",
                "300",
                "\u96E8\u304B\u96EA\u5F8C\u66C7",
                "RAIN OR SNOW, CLOUDY LATER",
            ],
            320: [
                "311.svg",
                "711.svg",
                "300",
                "\u671D\u306E\u5185\u96E8\u5F8C\u6674",
                "RAIN IN THE MORNING, CLEAR LATER",
            ],
            321: [
                "313.svg",
                "313.svg",
                "300",
                "\u671D\u306E\u5185\u96E8\u5F8C\u66C7",
                "RAIN IN THE MORNING, CLOUDY LATER",
            ],
            322: [
                "303.svg",
                "303.svg",
                "400",
                "\u96E8\u671D\u6669\u4E00\u6642\u96EA",
                "OCCASIONAL SNOW IN THE MORNING AND EVENING, RAIN DURING THE DAY",
            ],
            323: [
                "311.svg",
                "711.svg",
                "300",
                "\u96E8\u663C\u9803\u304B\u3089\u6674",
                "RAIN, CLEAR IN THE AFTERNOON",
            ],
            324: [
                "311.svg",
                "711.svg",
                "300",
                "\u96E8\u5915\u65B9\u304B\u3089\u6674",
                "RAIN, CLEAR IN THE EVENING",
            ],
            325: [
                "311.svg",
                "711.svg",
                "300",
                "\u96E8\u591C\u306F\u6674",
                "RAIN, CLEAR IN THE NIGHT",
            ],
            326: [
                "314.svg",
                "314.svg",
                "400",
                "\u96E8\u5915\u65B9\u304B\u3089\u96EA",
                "RAIN, SNOW IN THE EVENING",
            ],
            327: [
                "314.svg",
                "314.svg",
                "400",
                "\u96E8\u591C\u306F\u96EA",
                "RAIN,SNOW IN THE NIGHT",
            ],
            328: [
                "300.svg",
                "300.svg",
                "300",
                "\u96E8\u4E00\u6642\u5F37\u304F\u964D\u308B",
                "RAIN, EXPECT OCCASIONAL HEAVY RAINFALL",
            ],
            329: [
                "300.svg",
                "300.svg",
                "300",
                "\u96E8\u4E00\u6642\u307F\u305E\u308C",
                "RAIN, OCCASIONAL SLEET",
            ],
            340: ["400.svg", "400.svg", "400", "\u96EA\u304B\u96E8", "SNOWORRAIN"],
            350: [
                "300.svg",
                "300.svg",
                "300",
                "\u96E8\u3067\u96F7\u3092\u4F34\u3046",
                "RAIN AND THUNDER",
            ],
            361: [
                "411.svg",
                "811.svg",
                "400",
                "\u96EA\u304B\u96E8\u5F8C\u6674",
                "SNOW OR RAIN, CLEAR LATER",
            ],
            371: [
                "413.svg",
                "413.svg",
                "400",
                "\u96EA\u304B\u96E8\u5F8C\u66C7",
                "SNOW OR RAIN, CLOUDY LATER",
            ],
            400: ["400.svg", "400.svg", "400", "\u96EA", "SNOW"],
            401: [
                "401.svg",
                "801.svg",
                "400",
                "\u96EA\u6642\u3005\u6674",
                "SNOW, FREQUENT CLEAR",
            ],
            402: [
                "402.svg",
                "402.svg",
                "400",
                "\u96EA\u6642\u3005\u6B62\u3080",
                "SNOWTHROUGHOUT THE DAY",
            ],
            403: [
                "403.svg",
                "403.svg",
                "400",
                "\u96EA\u6642\u3005\u96E8",
                "SNOW,FREQUENT SCCATERED SHOWERS",
            ],
            405: ["400.svg", "400.svg", "400", "\u5927\u96EA", "HEAVYSNOW"],
            406: ["406.svg", "406.svg", "400", "\u98A8\u96EA\u5F37\u3044", "SNOWSTORM"],
            407: ["406.svg", "406.svg", "400", "\u66B4\u98A8\u96EA", "HEAVYSNOWSTORM"],
            409: [
                "403.svg",
                "403.svg",
                "400",
                "\u96EA\u4E00\u6642\u96E8",
                "SNOW, OCCASIONAL SCCATERED SHOWERS",
            ],
            411: [
                "411.svg",
                "811.svg",
                "400",
                "\u96EA\u5F8C\u6674",
                "SNOW,CLEAR LATER",
            ],
            413: [
                "413.svg",
                "413.svg",
                "400",
                "\u96EA\u5F8C\u66C7",
                "SNOW,CLOUDY LATER",
            ],
            414: ["414.svg", "414.svg", "400", "\u96EA\u5F8C\u96E8", "SNOW,RAIN LATER"],
            420: [
                "411.svg",
                "811.svg",
                "400",
                "\u671D\u306E\u5185\u96EA\u5F8C\u6674",
                "SNOW IN THE MORNING, CLEAR LATER",
            ],
            421: [
                "413.svg",
                "413.svg",
                "400",
                "\u671D\u306E\u5185\u96EA\u5F8C\u66C7",
                "SNOW IN THE MORNING, CLOUDY LATER",
            ],
            422: [
                "414.svg",
                "414.svg",
                "400",
                "\u96EA\u663C\u9803\u304B\u3089\u96E8",
                "SNOW, RAIN IN THE AFTERNOON",
            ],
            423: [
                "414.svg",
                "414.svg",
                "400",
                "\u96EA\u5915\u65B9\u304B\u3089\u96E8",
                "SNOW, RAIN IN THE EVENING",
            ],
            425: [
                "400.svg",
                "400.svg",
                "400",
                "\u96EA\u4E00\u6642\u5F37\u304F\u964D\u308B",
                "SNOW, EXPECT OCCASIONAL HEAVY SNOWFALL",
            ],
            426: [
                "400.svg",
                "400.svg",
                "400",
                "\u96EA\u5F8C\u307F\u305E\u308C",
                "SNOW, SLEET LATER",
            ],
            427: [
                "400.svg",
                "400.svg",
                "400",
                "\u96EA\u4E00\u6642\u307F\u305E\u308C",
                "SNOW, OCCASIONAL SLEET",
            ],
            450: [
                "400.svg",
                "400.svg",
                "400",
                "\u96EA\u3067\u96F7\u3092\u4F34\u3046",
                "SNOW AND THUNDER",
            ],
        }

        # Download svg
        url_base = "https://www.jma.go.jp/bosai/forecast/img/"
        download_dir = os.path.expanduser("~/Downloads/images/")
        os.makedirs(download_dir, exist_ok=True)
        for code in data.keys():
            svg_name = f"{code}.svg"
            url = f"{url_base}{svg_name}"

            response = requests.get(url, stream=True)

            if response.status_code == 200:
                with open(os.path.join(download_dir, svg_name), "wb") as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
                print(f"Downloaded {url}")
            else:
                print(f"Error downloading {url}")

        # Clear
        JmaWeatherCode.objects.all().delete()

        weather_code_list = [
            JmaConstWeatherCode(key, *values) for key, values in data.items()
        ]

        jma_weather_code_list = [
            JmaWeatherCode(
                code=x.code,
                image=x.image_day,
                summary_code=x.summary_code,
                name=x.name,
                name_en=x.name_en,
            )
            for x in weather_code_list
        ]
        JmaWeatherCode.objects.bulk_create(jma_weather_code_list)

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported all jma weather code master from manual data."
            )
        )
