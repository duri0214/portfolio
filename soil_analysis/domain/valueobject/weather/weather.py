from dataclasses import dataclass
from datetime import date, datetime


# マスタデータ
@dataclass
class WeatherCodeRaw:
    """
    気象庁の定数マスタ（天気コード）
    # TODO: クラス名を考えて（JmaConstWeatherRaw?）

    Attributes:
        code (str): The code of the weather.
        image_day (str): The image path for day weather.
        image_night (str): The image path for night weather.
        summary_code (str): The summary code for the weather.
        name (str): The name of the weather.
        name_en (str): The English name of the weather.
    """

    code: str
    image_day: str
    image_night: str
    summary_code: str
    name: str
    name_en: str


@dataclass
class JmaConst:
    """
    気象庁の定数マスタ（area, prefecture, region, city_group, city）
    # TODO: クラス名を考えて（JmaConstRaw? segment?）

    Attributes:
        code (str): The code of the constant.
        name (str): The name of the constant.
        children (list[str]): The list of children constants' codes.
        parent (str): The code of the parent constant.
    """

    code: str
    name: str
    children: list[str]
    parent: str


# 予報データ
@dataclass
class Region:
    """
    A class representing a region.

    Attributes:
        code (str): The code of the region.
        name (str): The name of the region.
    """

    code: str
    name: str


@dataclass
class SummaryData:
    """
    気象情報: [0]のサマリー情報

    Attributes:
        time_defined (datetime): "2024-08-29T17:00:00+09:00"
        code (str): "300"
        weather_summary (str): "雨　所により　雷を伴い　非常に　激しく　降る"
        wind_summary (str): "東の風　やや強く　海上　では　東の風　強く"
        wave_summary (str): "１．５メートル　ただし　淡路島南部　では　３メートル　うねり　を伴う"
    """

    time_defined: datetime
    code: str
    weather_summary: str
    wind_summary: str
    wave_summary: str


@dataclass
class AmedasRawData:
    """
    AmedasRawData

    A class representing raw weather data from the Amedas weather station.

    Attributes:
        code (str): The code identifying the Amedas weather station.
        name (str): The name of the Amedas weather station.
        temps (list[float]): The list of temperature 複数の日付の気温が混在している
    """

    code: str
    name: str
    temps: list[float]


class RegionTemperature:
    def __init__(
        self,
        region_code: str,
        region_name: str,
        data: dict,  # forecasts[0]["timeSeries"][2] 気温データが入っている
        compare_amedas_ids: list[str],
        target_date: date,
    ):
        self.region_code = region_code
        self.region_name = region_name
        self.data = data
        # expected_amedas_ids_in_region = [ # TODO: 外から取り込む（依存が強い）
        #     amedas.id for amedas in JmaAmedas.objects.filter(jma_area3_id=region_code)
        # ]
        temps_index = self.get_indexes_from_time_defines(
            data["timeDefines"], target_date
        )
        if len(temps_index) != 2:
            raise ValueError("気温の取得時、indexesの要素数が必ず2になります")

        # 気温を取り出す
        amedas_raw_data_list = [
            AmedasRawData(
                code=x["area"]["code"],
                name=x["area"]["name"],
                temps=list(map(float, x["temps"])),
            )
            for x in data["areas"]
        ]
        min_temps_list, max_temps_list = self.get_temps_list(
            amedas_raw_data_list, compare_amedas_ids, temps_index
        )
        self.avg_min_temps = round(sum(min_temps_list) / len(min_temps_list), 1)
        self.avg_max_temps = round(sum(max_temps_list) / len(max_temps_list), 1)

    @staticmethod
    def get_indexes_from_time_defines(
        time_defines: list[str], target_date: date
    ) -> list[int]:
        """
        target_date が time_defines のどの位置にあるかをインデックスのリストとして返します

        Args:
            time_defines: ["2023-03-17T00:00:00", "2023-03-18T00:00:00", "2023-03-18T09:00:00"]
            target_date: date(2023, 3, 18)

        Returns:
            [1, 2]

        Notes: つぎの工程（＝get_temps_list）で 1 と 2 の場所に最低気温と最高気温が入っている
        """
        time_defines = [
            datetime.fromisoformat(date_str).date() for date_str in time_defines
        ]

        return [
            i
            for i, time_define in enumerate(time_defines)
            if time_define == target_date
        ]

    @staticmethod
    def get_temps_list(
        amedas_raw_data_list: list[AmedasRawData],
        compare_amedas_ids: list[str],
        temps_index: list[int],
    ):
        """
        Args:
            amedas_raw_data_list: List of dictionaries containing amedas data.
            compare_amedas_ids: List of strings containing amedas ids for comparison.
            temps_index: List of integers representing the indexes of temperature values in amedas_data.

        Returns:
            A tuple containing two lists:
                min_temps_list: [18.1, 17.3]
                max_temps_list: [25.6, 23.9]

        Example Usage:
            22.5, 30.2 は前日データ、18.1, 25.6 は当日データとする
            ということは temp_indexes には [2, 3] が入っている
            amedas_data = [
                {
                    'area': {'code': 'A'},
                    'temps': [22.5, 30.2, 18.1, 25.6]
                },
                {
                    'area': {'code': 'B'},
                    'temps': [20.7, 28.8, 17.3, 23.9]
                },
            ]

            min_temps_list, max_temps_list = get_temps_list(amedas_data, compare_amedas_ids, temp_indexes)
        """
        min_temps_list, max_temps_list = [], []
        for amedas in amedas_raw_data_list:
            code = amedas.code
            min_temp = amedas.temps[temps_index[0]]
            max_temp = amedas.temps[temps_index[1]]
            if code not in compare_amedas_ids:
                # マスタにない「はぐれamedasコード」でした TODO: ログ出す？
                continue
            min_temps_list.append(min_temp)
            max_temps_list.append(max_temp)

        return min_temps_list, max_temps_list

    def __str__(self):
        return f"Avg Min: {self.avg_min_temps}℃, Avg Max: {self.avg_max_temps}℃"
