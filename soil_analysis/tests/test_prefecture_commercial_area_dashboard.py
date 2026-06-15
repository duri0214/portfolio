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

        prefecture_area_dashboard = PrefectureCommercialAreaService.build()
        shizuoka = self._find_area(prefecture_area_dashboard.areas, "静岡県")

        self.assertEqual(shizuoka.land_count, 1)
        self.assertEqual(shizuoka.company_count, 1)
        self.assertEqual(shizuoka.main_crop_name, "トマト")
        self.assertEqual(shizuoka.japan_map_code, 22)
        self.assertEqual(shizuoka.total_area, 12.5)
        self.assertEqual(shizuoka.warning_city_count, 1)
        self.assertEqual(shizuoka.status_label, "注意")
        self.assertGreater(shizuoka.risk_score, 30)

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
            area = JmaArea.objects.create(code=code, name=f"{prefecture_name}エリア")
            prefecture = JmaPrefecture.objects.create(
                code=code, name=prefecture_name, jma_area=area
            )
            region = JmaRegion.objects.create(
                code=f"{index:06d}",
                name=f"{prefecture_name}地域",
                jma_prefecture=prefecture,
            )
            city = JmaCity.objects.create(
                code=f"{index:07d}", name=f"{prefecture_name}市", jma_region=region
            )
            prefectures[prefecture_name] = {
                "prefecture": prefecture,
                "region": region,
                "city": city,
            }
        return prefectures
