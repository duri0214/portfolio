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
        - 期待値: 静岡県商圏に圃場数、企業数、主要作物、警報数、天気が反映されること。
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
        self.assertEqual(shizuoka.warning_summary, "大雨注意報")
        self.assertEqual(shizuoka.status_label, "注意")
        self.assertEqual(shizuoka.weather_name, "晴れ")
        self.assertEqual(shizuoka.weather_icon_image, "100.svg")
        self.assertEqual(shizuoka.weather_code, "100")
        self.assertEqual(shizuoka.weather_reporting_date, "2026-06-16")
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
        self.assertEqual(chiba.warning_summary, "大雨警報、洪水警報")
        self.assertEqual(chiba.weather_name, "雨")
        self.assertEqual(chiba.weather_code, "300")
        self.assertEqual(chiba.odds, 4.3)

    def test_build_groups_warning_names_without_showing_region_count(self):
        """
        シナリオ:
        - 入力: 埼玉県の複数地域に同名を含む警報・注意報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 地域件数ではなく、重複排除された警報・注意報名が表示用に返ること。
        """
        city = self._get_city("埼玉県")
        JmaWarning.objects.create(
            jma_region=city.jma_region,
            warnings="大雨注意報,雷注意報",
        )
        second_region = JmaRegion.objects.create(
            code="110002",
            name="埼玉県第2地域",
            jma_prefecture=city.jma_region.jma_prefecture,
        )
        JmaWarning.objects.create(
            jma_region=second_region,
            warnings="雷注意報",
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        saitama = self._find_area(prefecture_area_dashboard.areas, "埼玉県")

        self.assertEqual(saitama.warning_city_count, 2)
        self.assertEqual(saitama.warning_summary, "大雨注意報、雷注意報")

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
        self.assertEqual(yamagata.weather_reporting_date, "2026-06-17")

    def test_build_creates_sales_opportunity_to_warning_prefecture(self):
        """
        シナリオ:
        - 入力: 静岡県に晴れのトマト圃場、千葉県に雨と警報付きのトマト圃場があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 静岡県→千葉県の一方向売り込み候補が天気と警報由来の単一オッズ付きで返ること。
        """
        shizuoka_city = self._get_city("静岡県")
        chiba_city = self._get_city("千葉県")
        shizuoka_land = Land.objects.create(
            name="静岡トマト圃場",
            company=self.company,
            jma_city=shizuoka_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
        )
        chiba_land = Land.objects.create(
            name="千葉トマト圃場",
            company=self.company,
            jma_city=chiba_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.607,140.106",
        )
        LandLedger.objects.create(
            land=shizuoka_land,
            land_period=self.period,
            sampling_date="2026-03-01",
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        LandLedger.objects.create(
            land=chiba_land,
            land_period=self.period,
            sampling_date="2026-03-01",
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        JmaWarning.objects.create(jma_region=chiba_city.jma_region, warnings="大雨警報")
        JmaWeather.objects.create(
            jma_region=chiba_city.jma_region,
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

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        candidate = prefecture_area_dashboard.sales_opportunity_candidates[0]

        self.assertEqual(prefecture_area_dashboard.sales_opportunity_candidate_count, 1)
        self.assertEqual(candidate.relation_label, "静岡県→千葉県")
        self.assertEqual(candidate.target_name, "千葉県")
        self.assertEqual(candidate.main_crop_name, "トマト")
        self.assertEqual(candidate.odds, 4.2)
        self.assertEqual(
            candidate.odds,
            self._find_area(prefecture_area_dashboard.areas, "千葉県").odds,
        )
        self.assertIn("大雨警報", candidate.reason)
        self.assertIn("警報・注意報がない", candidate.reason)

    def test_dashboard_orders_areas_by_high_odds(self):
        """
        シナリオ:
        - 入力: 晴れの静岡県と雨警報の千葉県があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行し、オッズ順の商圏一覧を取得する。
        - 期待値: 天気が悪くオッズが高い千葉県が静岡県より前に並ぶこと。
        """
        shizuoka_city = self._get_city("静岡県")
        chiba_city = self._get_city("千葉県")
        Land.objects.create(
            name="静岡テスト圃場",
            company=self.company,
            jma_city=shizuoka_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
        )
        Land.objects.create(
            name="千葉テスト圃場",
            company=self.company,
            jma_city=chiba_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.607,140.106",
        )
        JmaWeather.objects.create(
            jma_region=shizuoka_city.jma_region,
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
        JmaWarning.objects.create(jma_region=chiba_city.jma_region, warnings="大雨警報")
        JmaWeather.objects.create(
            jma_region=chiba_city.jma_region,
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

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        area_names = [
            area.prefecture_name for area in prefecture_area_dashboard.areas_by_odds
        ]

        self.assertLess(area_names.index("千葉県"), area_names.index("静岡県"))

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
        self.assertContains(response, "地図から都道府県を選択")
        self.assertContains(response, "気象庁 全国予報マップ")
        self.assertContains(response, "晴れ系")
        self.assertContains(response, "くもり系")
        self.assertContains(response, "雨・雪系")
        self.assertContains(response, "天気未取得")
        self.assertContains(
            response,
            "https://www.jma.go.jp/bosai/map.html#5/29.555/141.395/&contents=forecast",
        )
        self.assertContains(response, "都道府県別商圏集計")
        self.assertContains(response, "これはオッズです。")
        self.assertContains(response, "雨系の出荷元の代わり")
        self.assertContains(response, "天気（予報日）")
        self.assertContains(response, '<th class="text-end">Odds</th>', html=True)
        self.assertContains(response, '<td class="fw-semibold">沖縄県</td>', html=True)
        self.assertContains(response, "圃場数")
        self.assertContains(response, "警報・注意報")
        self.assertContains(response, "なし")
        self.assertNotContains(response, '<th class="text-end">Risk</th>', html=True)
        self.assertContains(response, "天気未取得")
        self.assertNotContains(response, "<th>状態</th>", html=True)
        self.assertNotContains(response, "出荷信号")
        self.assertNotContains(response, "私は天気")
        self.assertContains(response, "赤信号県への売り込み候補")
        self.assertContains(response, "売り込み候補")
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
