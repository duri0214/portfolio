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
        self.cloudy_sometimes_sunny_weather_code = JmaWeatherCode.objects.create(
            code="201",
            summary_code="200",
            image="201.svg",
            name="曇時々晴",
            name_en="Cloudy, occasional sunny",
        )
        self.cloudy_then_rain_weather_code = JmaWeatherCode.objects.create(
            code="212",
            summary_code="300",
            image="212.svg",
            name="曇後一時雨",
            name_en="Cloudy, later occasional rain",
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
        - 期待値: 静岡県商圏に圃場数、企業数、登録作物、警報数、天気が反映されること。
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
        self.assertEqual(shizuoka.crop_names, ["トマト"])
        self.assertEqual(shizuoka.crop_summary, "トマト")
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
        self.assertEqual(chiba.weather_risk_index, 4.3)

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

    def test_build_uses_weather_code_first_two_digits_for_risk_index(self):
        """
        シナリオ:
        - 入力: 岐阜県に曇時々晴、愛知県に曇後一時雨、同数の注意報が登録されているDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 2xxを一律扱いせず、雨を含む愛知県のリスク指数が高くなること。
        """
        gifu_city = self._get_city("岐阜県")
        aichi_city = self._get_city("愛知県")
        JmaWarning.objects.create(jma_region=gifu_city.jma_region, warnings="雷注意報")
        JmaWarning.objects.create(
            jma_region=aichi_city.jma_region, warnings="濃霧注意報"
        )
        JmaWeather.objects.create(
            jma_region=gifu_city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.cloudy_sometimes_sunny_weather_code,
            weather_text="曇時々晴",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=20,
            avg_min_temperature=18,
            avg_max_temperature=28,
            avg_max_wind_speed=4,
        )
        JmaWeather.objects.create(
            jma_region=aichi_city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.cloudy_then_rain_weather_code,
            weather_text="曇後一時雨",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=60,
            avg_min_temperature=18,
            avg_max_temperature=25,
            avg_max_wind_speed=6,
        )

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        gifu = self._find_area(prefecture_area_dashboard.areas, "岐阜県")
        aichi = self._find_area(prefecture_area_dashboard.areas, "愛知県")

        self.assertEqual(gifu.weather_risk_index, 1.9)
        self.assertEqual(aichi.weather_risk_index, 3.4)
        self.assertGreater(aichi.weather_risk_index, gifu.weather_risk_index)

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
        - 入力: 静岡県に晴れのトマト圃場、岐阜県に晴れの別作物圃場、千葉県に雨と警報付きのトマト圃場があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 同じトマトを出せる静岡県→千葉県の売り込み候補と配車候補だけが天気リスク指数付きで返ること。
        """
        shizuoka_city = self._get_city("静岡県")
        gifu_city = self._get_city("岐阜県")
        chiba_city = self._get_city("千葉県")
        shizuoka_land = Land.objects.create(
            name="静岡トマト圃場",
            company=self.company,
            jma_city=shizuoka_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
        )
        gifu_land = Land.objects.create(
            name="岐阜きゅうり圃場",
            company=self.company,
            jma_city=gifu_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.423,136.761",
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
        cucumber = Crop.objects.create(name="きゅうり")
        LandLedger.objects.create(
            land=gifu_land,
            land_period=self.period,
            sampling_date="2026-03-01",
            analytical_agency=self.company,
            crop=cucumber,
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
        sales_candidate = prefecture_area_dashboard.sales_opportunity_candidates[0]
        dispatch_candidate = prefecture_area_dashboard.dispatch_candidates[0]

        self.assertEqual(
            len(prefecture_area_dashboard.all_sales_opportunity_candidates), 1
        )
        self.assertEqual(prefecture_area_dashboard.sales_opportunity_candidate_count, 1)
        self.assertEqual(sales_candidate.relation_label, "静岡県→千葉県")
        self.assertEqual(sales_candidate.target_name, "千葉県")
        self.assertEqual(sales_candidate.target_weather_icon_image, "300.svg")
        self.assertEqual(sales_candidate.main_crop_name, "トマト")
        self.assertEqual(sales_candidate.weather_risk_index, 4.2)
        self.assertEqual(
            sales_candidate.weather_risk_index,
            self._find_area(
                prefecture_area_dashboard.areas, "千葉県"
            ).weather_risk_index,
        )
        self.assertIn("大雨警報", sales_candidate.reason)
        self.assertIn("同じトマトを出せる", sales_candidate.reason)
        self.assertEqual(prefecture_area_dashboard.dispatch_candidate_count, 1)
        self.assertEqual(dispatch_candidate.relation_label, "静岡県→千葉県")
        self.assertEqual(dispatch_candidate.target_prefecture_name, "千葉県")
        self.assertEqual(dispatch_candidate.target_weather_icon_image, "300.svg")
        self.assertEqual(dispatch_candidate.weather_risk_index, 4.2)
        self.assertEqual(dispatch_candidate.logistics_status, "代替便確認中")
        self.assertFalse(hasattr(dispatch_candidate, "target_market_name"))
        self.assertFalse(hasattr(dispatch_candidate, "risk_score"))

    def test_build_creates_sales_opportunity_to_rainy_prefecture_by_same_crop(self):
        """
        シナリオ:
        - 入力: 静岡県に晴れのなばな圃場、三重県に雨で警報なしの3作物圃場があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 三重県の3作物が表示され、同じなばなを出せる静岡県が候補になること。
        """
        shizuoka_city = self._get_city("静岡県")
        mie_city = self._get_city("三重県")
        nabana = Crop.objects.create(name="なばな")
        tea = Crop.objects.create(name="茶")
        rice = Crop.objects.create(name="米")
        shizuoka_land = Land.objects.create(
            name="静岡なばな圃場",
            company=self.company,
            jma_city=shizuoka_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
        )
        mie_lands = [
            Land.objects.create(
                name=f"三重{crop.name}圃場",
                company=self.company,
                jma_city=mie_city,
                cultivation_type=self.cultivation_type,
                owner=self.user,
                center="34.730,136.508",
            )
            for crop in (tea, rice, nabana)
        ]
        LandLedger.objects.create(
            land=shizuoka_land,
            land_period=self.period,
            sampling_date="2026-03-01",
            analytical_agency=self.company,
            crop=nabana,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        for mie_land, crop in zip(mie_lands, (tea, rice, nabana), strict=True):
            LandLedger.objects.create(
                land=mie_land,
                land_period=self.period,
                sampling_date="2026-03-01",
                analytical_agency=self.company,
                crop=crop,
                sampling_method=self.sampling_method,
                sampling_staff=self.user,
            )
        JmaWeather.objects.create(
            jma_region=mie_city.jma_region,
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
        mie = self._find_area(prefecture_area_dashboard.areas, "三重県")
        candidate = prefecture_area_dashboard.sales_opportunity_candidates[0]

        self.assertEqual(mie.crop_names, ["なばな", "米", "茶"])
        self.assertEqual(mie.crop_summary, "なばな、米、茶")
        self.assertEqual(prefecture_area_dashboard.sales_opportunity_candidate_count, 1)
        self.assertEqual(candidate.relation_label, "静岡県→三重県")
        self.assertEqual(candidate.target_name, "三重県")
        self.assertEqual(candidate.main_crop_name, "なばな")
        self.assertEqual(candidate.weather_risk_index, 4.0)
        self.assertIn("雨", candidate.reason)

    def test_build_creates_sales_opportunity_from_lower_risk_warning_prefecture(self):
        """
        シナリオ:
        - 入力: 秋田県に注意報つきの米圃場、兵庫県に低リスクの米圃場、山形県により高い天気リスクの米圃場があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 秋田県に注意報があっても、隣接県で同じ米を出せるため遠方の兵庫県より優先されること。
        """
        akita_city = self._get_city("秋田県")
        hyogo_city = self._get_city("兵庫県")
        yamagata_city = self._get_city("山形県")
        yamagata_prefecture = yamagata_city.jma_region.jma_prefecture
        yamagata_prefecture.jma_area = akita_city.jma_region.jma_prefecture.jma_area
        yamagata_prefecture.save()
        rice = Crop.objects.create(name="米")
        akita_land = Land.objects.create(
            name="秋田米圃場",
            company=self.company,
            jma_city=akita_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="39.720,140.103",
        )
        hyogo_land = Land.objects.create(
            name="兵庫米圃場",
            company=self.company,
            jma_city=hyogo_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.691,135.183",
        )
        yamagata_land = Land.objects.create(
            name="山形米圃場",
            company=self.company,
            jma_city=yamagata_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="38.240,140.363",
        )
        for land in (akita_land, hyogo_land, yamagata_land):
            LandLedger.objects.create(
                land=land,
                land_period=self.period,
                sampling_date="2026-03-01",
                analytical_agency=self.company,
                crop=rice,
                sampling_method=self.sampling_method,
                sampling_staff=self.user,
            )
        JmaWarning.objects.create(jma_region=akita_city.jma_region, warnings="雷注意報")
        JmaWeather.objects.create(
            jma_region=akita_city.jma_region,
            reporting_date=date(2026, 6, 16),
            jma_weather_code=self.cloudy_sometimes_sunny_weather_code,
            weather_text="曇時々晴",
            wind_text="北の風",
            wave_text="なし",
            avg_rain_probability=30,
            avg_min_temperature=18,
            avg_max_temperature=25,
            avg_max_wind_speed=5,
        )
        JmaWarning.objects.create(
            jma_region=yamagata_city.jma_region, warnings="濃霧注意報,雷注意報"
        )
        JmaWeather.objects.create(
            jma_region=yamagata_city.jma_region,
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

        self.assertEqual(candidate.relation_label, "秋田県→山形県")
        self.assertEqual(candidate.main_crop_name, "米")
        self.assertEqual(candidate.weather_risk_index, 4.2)
        self.assertEqual(candidate.origin_weather_risk_index, 1.9)
        self.assertIn("天気リスク指数が1.9", candidate.reason)

    def test_dashboard_orders_areas_by_high_weather_risk(self):
        """
        シナリオ:
        - 入力: 晴れの静岡県と雨警報の千葉県があるDB状態。
        - 処理: 都道府県別商圏Serviceを実行し、リスク指数順の商圏一覧を取得する。
        - 期待値: 天気が悪くリスク指数が高い千葉県が静岡県より前に並ぶこと。
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
            area.prefecture_name
            for area in prefecture_area_dashboard.areas_by_weather_risk
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
        - 期待値: 日本地図と全国商圏リスクランキングが表示され、個別判断用の一覧は表示されないこと。
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
        self.assertIn("jmaAreaName", response.context["commercial_area_map_data"][0])
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
        self.assertContains(response, "全国商圏リスクランキング")
        self.assertContains(
            response, "これは天気リスクを織り込んだ全国ランキングです。"
        )
        self.assertContains(response, "詳細ページで深掘りする商圏")
        self.assertContains(response, "天気（予報日）")
        self.assertContains(response, '<th class="text-end">リスク指数</th>', html=True)
        self.assertContains(
            response,
            '<td class="fw-semibold"><a href="/soil_analysis/prefecture/47/detail" class="text-decoration-none">沖縄県</a></td>',
            html=True,
        )
        self.assertContains(response, "圃場数")
        self.assertContains(response, "警報・注意報")
        self.assertContains(response, "なし")
        self.assertNotContains(response, '<th class="text-end">Risk</th>', html=True)
        self.assertContains(response, "天気未取得")
        self.assertNotContains(response, "<th>状態</th>", html=True)
        self.assertNotContains(response, "出荷信号")
        self.assertNotContains(response, "私は天気")
        self.assertContains(response, "注意商圏")
        self.assertNotContains(response, "天気リスク県への売り込み候補")
        self.assertNotContains(response, "売り込み候補")
        self.assertNotContains(response, "配車候補キュー")
        self.assertNotContains(response, "企業別圃場一覧")
        self.assertContains(response, reverse("soil:prefecture_detail", args=[22]))
        self.assertContains(response, "静岡県")

    def test_prefecture_detail_view_displays_area_candidates_and_lands(self):
        """
        シナリオ:
        - 入力: 静岡県・愛知県から千葉県へ売り込めるトマト圃場と、千葉県の雨天リスクがあるDB状態。
        - 処理: 千葉県の都道府県詳細ページを表示する。
        - 期待値: 詳細ページでは同じ売り込み先への複数候補が表示され、配車候補は重複表示されないこと。
        """
        shizuoka_city = self._get_city("静岡県")
        aichi_city = self._get_city("愛知県")
        chiba_city = self._get_city("千葉県")
        shizuoka_land = Land.objects.create(
            name="静岡トマト圃場",
            company=self.company,
            jma_city=shizuoka_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="34.74424,137.64905",
            area=12.5,
        )
        aichi_land = Land.objects.create(
            name="愛知トマト圃場",
            company=self.company,
            jma_city=aichi_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.180,136.906",
        )
        chiba_land = Land.objects.create(
            name="千葉トマト圃場",
            company=self.company,
            jma_city=chiba_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="35.607,140.106",
        )
        for land in (shizuoka_land, aichi_land, chiba_land):
            LandLedger.objects.create(
                land=land,
                land_period=self.period,
                sampling_date="2026-03-01",
                analytical_agency=self.company,
                crop=self.crop,
                sampling_method=self.sampling_method,
                sampling_staff=self.user,
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
        JmaWeather.objects.create(
            jma_region=aichi_city.jma_region,
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

        response = self.client.get(reverse("soil:prefecture_detail", args=[12]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["area"].prefecture_name, "千葉県")
        self.assertEqual(len(response.context["sales_opportunity_candidates"]), 2)
        self.assertContains(response, "千葉県 詳細")
        self.assertContains(response, "千葉県エリア")
        self.assertContains(response, "雨")
        self.assertContains(response, "market-weather-value")
        self.assertContains(response, "market-kpi-meta")
        self.assertContains(response, "天気リスク指数")
        self.assertContains(response, "静岡県→千葉県")
        self.assertContains(response, "愛知県→千葉県")
        self.assertContains(response, "千葉トマト圃場")
        self.assertNotContains(response, "静岡トマト圃場")
        self.assertNotContains(response, "愛知トマト圃場")
        self.assertNotContains(response, "配車候補キュー")

    def test_prefecture_detail_view_displays_empty_state_without_land(self):
        """
        シナリオ:
        - 入力: 47都道府県マスタのみで沖縄県に圃場や売り込み候補がないDB状態。
        - 処理: 沖縄県の都道府県詳細ページを表示する。
        - 期待値: 画面が壊れず、売り込み候補と圃場一覧の空状態が表示されること。
        """
        response = self.client.get(reverse("soil:prefecture_detail", args=[47]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "沖縄県 詳細")
        self.assertContains(response, "沖縄県 に関係する売り込み候補はありません。")
        self.assertContains(response, "沖縄県 に登録済みの圃場はありません。")

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
