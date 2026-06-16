from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.domain.service.prefecture_commercial_area import (
    JAPAN_MAP_PREFECTURES,
    PrefectureCommercialAreaService,
)
from soil_analysis.models import (
    Company,
    CompanyCategory,
    Crop,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    JmaWeather,
    JmaWeatherCode,
    JmaWarning,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
)


class PrefectureCommercialAreaDashboardTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="market-user")
        self.category = CompanyCategory.objects.create(name="農業法人")
        self.company = Company.objects.create(
            name="全国テスト農園", category=self.category
        )
        self.cultivation_type = CultivationType.objects.create(name="露地")
        self.crop = Crop.objects.create(name="トマト")
        self.sunny_weather_code = JmaWeatherCode.objects.create(
            code="100",
            summary_code="100",
            image="100.svg",
            name="晴れ",
            name_en="Sunny",
        )
        self.rainy_weather_code = JmaWeatherCode.objects.create(
            code="300",
            summary_code="300",
            image="300.svg",
            name="雨",
            name_en="Rain",
        )
        self.sunny_then_rain_weather_code = JmaWeatherCode.objects.create(
            code="102",
            summary_code="300",
            image="102.svg",
            name="晴一時雨",
            name_en="Clear, occasional rain",
        )
        self.period = LandPeriod.objects.create(year=2026, name="播種時")
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        self.prefectures = self._create_prefectures()

    def test_build_creates_commercial_area_for_all_prefectures(self):
        """
        シナリオ:
        - 入力: 47都道府県のJMA都道府県マスタ。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 47件の商圏VOが作成され、未登録商圏も表示対象に含まれること。
        """
        prefecture_area_dashboard = PrefectureCommercialAreaService.build()

        self.assertEqual(prefecture_area_dashboard.area_count, 47)
        self.assertEqual(prefecture_area_dashboard.active_area_count, 0)
        self.assertEqual(prefecture_area_dashboard.areas[0].status_label, "未登録")

    def test_build_aggregates_prefecture_land_crop_and_warning(self):
        """
        シナリオ:
        - 入力: 静岡県に圃場、作物台帳、JMA警報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 静岡県商圏に圃場数、企業数、主要作物、警報数、リスクが反映されること。
        """
        city = self._get_city("静岡県")
        land = Land.objects.create(
            name="静岡テスト圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
            area=12.5,
        )
        LandLedger.objects.create(
            land=land,
            land_period=self.period,
            sampling_date="2026-03-01",
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        JmaWarning.objects.create(jma_region=city.jma_region, warnings="大雨注意報")
        JmaWeather.objects.create(
            jma_region=city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.sunny_weather_code,
            weather_text="晴れ",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=10,
            avg_min_temperature=18,
            avg_max_temperature=28,
            avg_max_wind_speed=4,
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        shizuoka = self._find_area(prefecture_area_dashboard.areas, "静岡県")

        self.assertEqual(shizuoka.land_count, 1)
        self.assertEqual(shizuoka.company_count, 1)
        self.assertEqual(shizuoka.main_crop_name, "トマト")
        self.assertEqual(shizuoka.japan_map_code, 22)
        self.assertEqual(shizuoka.total_area, 12.5)
        self.assertEqual(shizuoka.warning_city_count, 1)
        self.assertEqual(shizuoka.status_label, "注意")
        self.assertEqual(shizuoka.weather_name, "晴れ")
        self.assertEqual(shizuoka.weather_icon_image, "100.svg")
        self.assertEqual(shizuoka.weather_code, "100")
        self.assertGreater(shizuoka.risk_score, 30)

    def test_build_uses_rainy_weather_for_prefecture_map_color_source(self):
        """
        シナリオ:
        - 入力: 千葉県に圃場、雨の天気、複数のJMA警報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 千葉県商圏に雨天の集計用コードが入り、地図色の判定元になること。
        """
        city = self._get_city("千葉県")
        Land.objects.create(
            name="千葉テスト圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.607,140.106",
        )
        JmaWarning.objects.create(jma_region=city.jma_region, warnings="大雨警報")
        JmaWeather.objects.create(
            jma_region=city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.rainy_weather_code,
            weather_text="雨",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=80,
            avg_min_temperature=18,
            avg_max_temperature=22,
            avg_max_wind_speed=8,
        )
        second_region = JmaRegion.objects.create(
            code="120002",
            name="千葉県第2地域",
            jma_prefecture=city.jma_region.jma_prefecture,
        )
        JmaWarning.objects.create(jma_region=second_region, warnings="洪水警報")

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        chiba = self._find_area(prefecture_area_dashboard.areas, "千葉県")

        self.assertEqual(chiba.warning_city_count, 2)
        self.assertEqual(chiba.weather_name, "雨")
        self.assertEqual(chiba.weather_code, "300")

    def test_build_keeps_sunny_weather_code_even_with_warning(self):
        """
        シナリオ:
        - 入力: 山形県に晴れの天気とJMA警報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 表示天気が晴れの場合、警報件数だけで雨天扱いにならないこと。
        """
        city = self._get_city("山形県")
        JmaWarning.objects.create(jma_region=city.jma_region, warnings="乾燥注意報")
        JmaWeather.objects.create(
            jma_region=city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.sunny_weather_code,
            weather_text="晴れ",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=10,
            avg_min_temperature=18,
            avg_max_temperature=28,
            avg_max_wind_speed=4,
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        yamagata = self._find_area(prefecture_area_dashboard.areas, "山形県")

        self.assertEqual(yamagata.weather_name, "晴れ")
        self.assertEqual(yamagata.warning_city_count, 1)
        self.assertEqual(yamagata.weather_code, "100")

    def test_build_uses_weather_code_first_digit_for_map_color_source(self):
        """
        シナリオ:
        - 入力: 山形県に今日の雨予報と明日の晴一時雨予報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 一番未来の明日予報を使い、集計用コードではなく天気コードが入ること。
        """
        city = self._get_city("山形県")
        JmaWeather.objects.create(
            jma_region=city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.rainy_weather_code,
            weather_text="雨",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=80,
            avg_min_temperature=18,
            avg_max_temperature=22,
            avg_max_wind_speed=8,
        )
        JmaWeather.objects.create(
            jma_region=city.jma_region,
            reporting_date=date(2026, 6, 17),
            jma_weather_code=self.sunny_then_rain_weather_code,
            weather_text="晴一時雨",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=40,
            avg_min_temperature=18,
            avg_max_temperature=28,
            avg_max_wind_speed=4,
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        yamagata = self._find_area(prefecture_area_dashboard.areas, "山形県")

        self.assertEqual(yamagata.weather_name, "晴一時雨")
        self.assertEqual(yamagata.weather_icon_image, "102.svg")
        self.assertEqual(yamagata.weather_code, "102")

    def test_build_groups_split_jma_prefecture_rows_into_one_prefecture(self):
        """
        シナリオ:
        - 入力: 北海道内のJMA府県予報区である宗谷地方に圃場が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 宗谷地方が日本地図上の北海道商圏へ集約され、KeyErrorにならないこと。
        """
        city = self._get_city("宗谷地方")
        Land.objects.create(
            name="宗谷テスト圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="45.415,141.673",
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        hokkaido = self._find_area(prefecture_area_dashboard.areas, "北海道")

        self.assertEqual(prefecture_area_dashboard.area_count, 47)
        self.assertEqual(hokkaido.japan_map_code, 1)
        self.assertEqual(hokkaido.land_count, 1)

    def test_build_raises_error_when_jma_prefecture_code_is_not_prefecture_code(self):
        """
        シナリオ:
        - 入力: 1から47の都道府県コードへ変換できないJMA府県予報区コードの圃場。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: データ不整合としてValueErrorが発生すること。
        """
        city = self._create_city("不明地域", "990000")
        Land.objects.create(
            name="不明地域テスト圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.0,135.0",
        )

        with self.assertRaisesMessage(
            ValueError, "1から47の都道府県コードに対応していません"
        ):
            PrefectureCommercialAreaService.build()

    def test_home_view_displays_prefecture_commercial_area_dashboard(self):
        """
        シナリオ:
        - 入力: 47都道府県マスタと静岡県の圃場が登録されているDB状態。
        - 処理: soil_analysis のトップページを表示する。
        - 期待値: 日本地図、都道府県別商圏集計、配車候補、既存企業別圃場一覧が表示されること。
        """
        city = self._get_city("静岡県")
        Land.objects.create(
            name="静岡テスト圃場",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
        )

        response = self.client.get(reverse("soil:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["prefecture_area_dashboard"].area_count, 47)
        self.assertEqual(len(response.context["commercial_area_map_data"]), 47)
        self.assertContains(response, "都道府県別商圏マップ")
        self.assertContains(response, "日本地図商圏マップ")
        self.assertContains(response, "都道府県別商圏集計")
        self.assertContains(response, "天気")
        self.assertNotContains(response, "<th>状態</th>", html=True)
        self.assertNotContains(response, "出荷信号")
        self.assertNotContains(response, "私は天気")
        self.assertContains(response, "配車候補キュー")
        self.assertContains(response, "企業別圃場一覧")
        self.assertContains(response, "静岡県")

    @staticmethod
    def _find_area(areas, prefecture_name):
        return next(area for area in areas if area.prefecture_name == prefecture_name)

    def _get_city(self, prefecture_name):
        return self.prefectures[prefecture_name]["city"]

    @staticmethod
    def _create_prefectures():
        prefectures = {}
        for index, prefecture_name in enumerate(
            [name for _, name in JAPAN_MAP_PREFECTURES] + ["宗谷地方"], start=1
        ):
            code = "011000" if prefecture_name == "宗谷地方" else f"{index:02d}0000"
            city = PrefectureCommercialAreaDashboardTest._create_city(
                prefecture_name, code, index
            )
            prefectures[prefecture_name] = {
                "city": city,
            }
        return prefectures

    @staticmethod
    def _create_city(prefecture_name, prefecture_code, sequence=999):
        area = JmaArea.objects.create(
            code=prefecture_code, name=f"{prefecture_name}エリア"
        )
        prefecture = JmaPrefecture.objects.create(
            code=prefecture_code, name=prefecture_name, jma_area=area
        )
        region = JmaRegion.objects.create(
            code=f"{sequence:06d}",
            name=f"{prefecture_name}地域",
            jma_prefecture=prefecture,
        )
        return JmaCity.objects.create(
            code=f"{sequence:07d}", name=f"{prefecture_name}市", jma_region=region
        )
