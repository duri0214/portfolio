from dataclasses import dataclass
from datetime import datetime, date


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
class MeanCalculable:
    """
    平均を出すための生値とその平均値

    Args:
        float_list (list[float]): 生値
    """

    def __init__(self, float_list: list[float]) -> None:
        self.raw: list[float] = float_list
        self.mean: float = (
            round(sum(float_list) / len(float_list), 1) if float_list else 0
        )


@dataclass(frozen=True)
class Region:
    """
    A class representing a region.

    Attributes:
        code (str): "280010"
        name (str): "南部"
    """

    code: str
    name: str


@dataclass(frozen=True)
class SummaryText:
    """
    気象情報: サマリー情報

    Attributes:
        weather (str): "雨　所により　雷を伴い　非常に　激しく　降る"
        wind (str): "東の風　やや強く　海上　では　東の風　強く"
        wave (str): "１．５メートル　ただし　淡路島南部　では　３メートル　うねり　を伴う"
    """

    weather: str
    wind: str
    wave: str


@dataclass(frozen=True)
class RainData:
    """
    気象情報: 降水確率

    Attributes:
        values (MeanCalculable): 生値とその平均値（時間帯平均）
        unit (str): "%"
    """

    values: MeanCalculable
    unit: str = "%"


@dataclass(frozen=True)
class TemperatureData:
    """
    気象情報: 気温

    Attributes:
        min_values (MeanCalculable): 生値とその平均値（region平均）
        max_values (MeanCalculable): 生値とその平均値（region平均）
        unit (str): "℃"
    """

    min_values: MeanCalculable
    max_values: MeanCalculable
    unit: str = "℃"


class WindData:
    """
    気象情報: 最大風速

    Attributes:
        values (MeanCalculable): 生値とその平均値（時間帯平均）
        unit (str): "以下" or "メートル毎秒"

    Notes: 風速値が9のばあい、その object に condition というキーが現れて "以下" という値が入るが
     表現を間引いて、平均値が9以下だったら "以下" にすることにした
    """

    def __init__(self, values: MeanCalculable):
        self.values = values
        self.unit = "以下" if self.values.mean <= 9 else "メートル毎秒"

    def __str__(self):
        return f"最大風速（時間帯平均）は {self.values.mean} {self.unit}"


@dataclass(frozen=True)
class WeatherData:
    """
    気象情報: 1日分の天気情報

    Attributes:

    Attributes:
        time_defined (datetime): "2024-08-29T17:00:00+09:00"
        code (str): "300"
        summary_text (SummaryText): "雨　所により　雷を伴い　非常に　激しく　降る"
        rain_data (RainData): "60%"
        temperature_data (TemperatureData): "25℃"
        wind_data (WindData): 9以下
    """

    time_defined: datetime
    code: str
    summary_text: SummaryText
    rain_data: RainData
    temperature_data: TemperatureData
    wind_data: WindData


class WeatherForecast:
    """
    気象情報: 何日ぶんかの天気情報を持った天気予報

    Args:
        region (Region): The region for which the weather forecast is generated.
        weather_data (list[WeatherData]): A list of WeatherData objects representing the forecast data.

    Attributes:
        region (Region): The region for which the weather forecast is generated.
        weather_data (list[WeatherData]): A list of WeatherData objects representing the forecast data.
    """

    def __init__(
        self,
        region: Region,
        weather_data: list[WeatherData],
    ):
        self.region = region
        self.weather_data = weather_data


class XXXTemperatureData:
    # TODO: Regionの文字はいらないんじゃない？（WeatherForecastがいいかな）
    @dataclass
    class AmedasData:
        """
        気象情報: [1]の雨量情報

        A class representing raw weather data from the Amedas weather station.

        Attributes:
            code (str): The code identifying the Amedas weather station.
            name (str): The name of the Amedas weather station.
            temps (list[float]): The list of temperature 複数の日付の気温が混在している
        """

        code: str
        name: str
        temps: list[float]

    def __init__(
        self,
        region_code: str,
        region_name: str,
        data: dict,  # forecasts[0]["timeSeries"][2] 気温データが入っている TODO: data: WeatherRawData がいいかな
        compare_amedas_ids: list[str],
        target_date: date,
    ):
        # TODO: self.region: Region がよさそう
        self.region_code = region_code
        self.region_name = region_name
        self.data = data

        temps_index = self.get_indexes_from_time_defines(
            data["timeDefines"], target_date
        )
        if len(temps_index) != 2:
            raise ValueError("気温の取得時、indexesの要素数が必ず2になります")

        # 気温を取り出す
        amedas_raw_data_list = [
            self.AmedasData(
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
        amedas_raw_data_list: list[AmedasData],
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
