from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from soil_analysis.domain.service.prefecture_commercial_area import (
    JAPAN_MAP_PREFECTURES,
    PrefectureCommercialAreaService,
)
from soil_analysis.management.commands.generate_prefecture_representative_fixtures import (
    PREFECTURE_REPRESENTATIVE_CROPS,
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
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
    UserAttribute,
)


class PrefectureRepresentativeFixtureCommandTest(TestCase):
    def test_command_creates_three_representative_lands_per_prefecture(self):
        """
        シナリオ:
        - 入力: 47都道府県分のJMA市区町村と、会社・作型・時期・採土法の参照マスタ。
        - 処理: 代表作物つき圃場データ作成コマンドを実行する。
        - 期待値: 各都道府県に代表作物3つ分のCrop、Land、LandLedgerが作成されること。
        """
        self._create_reference_masters()

        call_command("generate_prefecture_representative_fixtures", verbosity=0)

        self.assertEqual(Land.objects.count(), 47 * 3)
        self.assertEqual(LandLedger.objects.count(), 47 * 3)
        self.assertEqual(Crop.objects.count(), 65)

        for prefecture_index, prefecture_name in JAPAN_MAP_PREFECTURES:
            prefecture_code = f"prefecture_code={prefecture_index:02d}"
            prefecture_lands = Land.objects.filter(remark__contains=prefecture_code)
            self.assertEqual(prefecture_lands.count(), 3, prefecture_name)

            crop_names = list(
                LandLedger.objects.filter(land__in=prefecture_lands)
                .order_by("id")
                .values_list("crop__name", flat=True)
            )
            self.assertEqual(
                crop_names,
                list(PREFECTURE_REPRESENTATIVE_CROPS[prefecture_name]),
            )

    def test_command_is_idempotent(self):
        """
        シナリオ:
        - 入力: 代表作物つき圃場データを一度作成済みのDB状態。
        - 処理: 同じコマンドを再実行する。
        - 期待値: Crop、Land、LandLedgerが重複せず、件数が維持されること。
        """
        self._create_reference_masters()

        call_command("generate_prefecture_representative_fixtures", verbosity=0)
        call_command("generate_prefecture_representative_fixtures", verbosity=0)

        self.assertEqual(Land.objects.count(), 47 * 3)
        self.assertEqual(LandLedger.objects.count(), 47 * 3)
        self.assertEqual(Crop.objects.count(), 65)

    def test_command_data_can_be_aggregated_by_national_market_vo(self):
        """
        シナリオ:
        - 入力: 代表作物つき圃場データを作成済みのDB状態。
        - 処理: 都道府県別商圏Serviceを実行する。
        - 期待値: 47都道府県すべてに3圃場が入り、主要作物が未設定にならないこと。
        """
        self._create_reference_masters()
        call_command("generate_prefecture_representative_fixtures", verbosity=0)

        dashboard = PrefectureCommercialAreaService.build()

        self.assertEqual(dashboard.active_area_count, 47)
        self.assertEqual(dashboard.land_count, 47 * 3)
        self.assertTrue(all(area.land_count == 3 for area in dashboard.areas))
        self.assertTrue(
            all(area.main_crop_name != "未設定" for area in dashboard.areas)
        )

    def _create_reference_masters(self):
        sampling_staff = get_user_model().objects.create(
            id=19, username="sampling-staff"
        )
        owner = get_user_model().objects.create(id=21, username="prefecture-owner")
        CompanyCategory.objects.create(id=1, name="農業法人")
        CompanyCategory.objects.create(id=2, name="分析機関")
        Company.objects.create(id=1, name="土壌分析テスト法人", category_id=1)
        Company.objects.create(id=2, name="全国代表作物分析機関", category_id=2)
        UserAttribute.objects.create(
            user=sampling_staff,
            role=UserAttribute.Role.STAFF,
            organization="土掘りチーム",
        )
        UserAttribute.objects.create(
            user=owner,
            role=UserAttribute.Role.OWNER,
            organization="土壌分析テスト法人",
        )
        CultivationType.objects.create(id=1, name="露地")
        LandPeriod.objects.create(id=1, year=2026, name="播種時")
        SamplingMethod.objects.create(id=1, name="5点法", times=5)

        for prefecture_code, prefecture_name in JAPAN_MAP_PREFECTURES:
            jma_code = f"{prefecture_code:02d}0000"
            area = JmaArea.objects.create(
                code=jma_code, name=f"{prefecture_name}エリア"
            )
            prefecture = JmaPrefecture.objects.create(
                code=jma_code, name=prefecture_name, jma_area=area
            )
            region = JmaRegion.objects.create(
                code=f"{prefecture_code:02d}0010",
                name=f"{prefecture_name}地域",
                jma_prefecture=prefecture,
            )
            JmaCity.objects.create(
                code=f"{prefecture_code:02d}00100",
                name=f"{prefecture_name}代表市",
                jma_region=region,
            )
