from django.core.management.base import BaseCommand, CommandError

from soil_analysis.domain.service.prefecture_commercial_area import (
    JAPAN_MAP_PREFECTURES,
)
from soil_analysis.models import (
    Company,
    Crop,
    CultivationType,
    JmaCity,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
    UserAttribute,
)


SOURCE_NOTE = (
    "農林水産省 作物統計およびe-Stat 作物統計調査の都道府県別作付・収穫量を参考にした"
    "全国商圏ダッシュボード用代表作物"
)

PREFECTURE_REPRESENTATIVE_CROPS = {
    "北海道": ("ばれいしょ", "てんさい", "小麦"),
    "青森県": ("りんご", "にんにく", "ながいも"),
    "岩手県": ("りんご", "米", "ほうれんそう"),
    "宮城県": ("米", "いちご", "大豆"),
    "秋田県": ("米", "えだまめ", "りんご"),
    "山形県": ("さくらんぼ", "米", "西洋なし"),
    "福島県": ("もも", "米", "きゅうり"),
    "茨城県": ("れんこん", "メロン", "はくさい"),
    "栃木県": ("いちご", "にら", "米"),
    "群馬県": ("こんにゃくいも", "キャベツ", "ねぎ"),
    "埼玉県": ("ねぎ", "こまつな", "さといも"),
    "千葉県": ("らっかせい", "だいこん", "ねぎ"),
    "東京都": ("こまつな", "ほうれんそう", "トマト"),
    "神奈川県": ("だいこん", "キャベツ", "みかん"),
    "新潟県": ("米", "えだまめ", "すいか"),
    "富山県": ("米", "チューリップ", "大豆"),
    "石川県": ("米", "だいこん", "すいか"),
    "福井県": ("米", "そば", "らっきょう"),
    "山梨県": ("ぶどう", "もも", "すもも"),
    "長野県": ("レタス", "りんご", "ぶどう"),
    "岐阜県": ("ほうれんそう", "柿", "トマト"),
    "静岡県": ("茶", "みかん", "なばな"),
    "愛知県": ("キャベツ", "トマト", "いちじく"),
    "三重県": ("茶", "米", "なばな"),
    "滋賀県": ("米", "麦", "大豆"),
    "京都府": ("茶", "九条ねぎ", "京みずな"),
    "大阪府": ("なす", "しゅんぎく", "ぶどう"),
    "兵庫県": ("米", "たまねぎ", "丹波黒大豆"),
    "奈良県": ("柿", "いちご", "茶"),
    "和歌山県": ("みかん", "梅", "柿"),
    "鳥取県": ("梨", "らっきょう", "すいか"),
    "島根県": ("米", "ぶどう", "メロン"),
    "岡山県": ("もも", "ぶどう", "米"),
    "広島県": ("レモン", "みかん", "米"),
    "山口県": ("米", "みかん", "はなっこりー"),
    "徳島県": ("すだち", "にんじん", "れんこん"),
    "香川県": ("オリーブ", "ブロッコリー", "レタス"),
    "愛媛県": ("みかん", "キウイフルーツ", "米"),
    "高知県": ("なす", "しょうが", "ゆず"),
    "福岡県": ("いちご", "米", "小麦"),
    "佐賀県": ("米", "たまねぎ", "いちご"),
    "長崎県": ("ばれいしょ", "びわ", "みかん"),
    "熊本県": ("トマト", "すいか", "米"),
    "大分県": ("かぼす", "乾しいたけ", "ねぎ"),
    "宮崎県": ("きゅうり", "ピーマン", "マンゴー"),
    "鹿児島県": ("さつまいも", "茶", "さとうきび"),
    "沖縄県": ("さとうきび", "パイナップル", "マンゴー"),
}


class Command(BaseCommand):
    help = "47都道府県の代表作物つき圃場データを作成します。"

    def handle(self, *args, **options):
        """
        JMA市区町村マスタをもとに、47都道府県それぞれへ代表圃場と作物台帳を作成します。

        `weather_load_const_master` でJMAマスタを読み込み、会社・作型・時期・採土法の
        参照マスタを投入した後に実行する想定です。代表作物は農林水産省 作物統計および
        e-Stat 作物統計調査を参考にし、厳密な順位再現よりも全国市場VO上で
        都道府県らしさが出ることを優先します。
        """
        cities_by_prefecture = self._get_representative_cities()
        references = self._get_references()
        crop_id_by_name = self._build_crop_id_by_name()

        crops = self._create_crops(crop_id_by_name)
        lands = self._create_lands(cities_by_prefecture, references)
        self._create_land_ledgers(crops, lands, references)

        self.stdout.write(
            self.style.SUCCESS("47都道府県 x 3代表作物の圃場データを作成しました。")
        )

    @staticmethod
    def _get_representative_cities() -> dict[str, JmaCity]:
        cities_by_code = {}
        cities = JmaCity.objects.select_related("jma_region__jma_prefecture").order_by(
            "id"
        )
        for city in cities:
            prefecture_code = int(city.jma_region.jma_prefecture.code[:2])
            if 1 <= prefecture_code <= 47 and prefecture_code not in cities_by_code:
                cities_by_code[prefecture_code] = city

        missing_prefectures = [
            name
            for prefecture_code, name in JAPAN_MAP_PREFECTURES
            if prefecture_code not in cities_by_code
        ]
        if missing_prefectures:
            raise CommandError(
                "JMA市区町村マスタが不足しています。"
                "先に python manage.py weather_load_const_master を実行してください: "
                + ", ".join(missing_prefectures)
            )

        return {
            name: cities_by_code[prefecture_code]
            for prefecture_code, name in JAPAN_MAP_PREFECTURES
        }

    @staticmethod
    def _get_references() -> dict[str, object]:
        try:
            references = {
                "company": Company.objects.get(pk=1),
                "analytical_agency": Company.objects.get(pk=2),
                "cultivation_type": CultivationType.objects.get(pk=1),
                "land_period": LandPeriod.objects.get(pk=1),
                "sampling_method": SamplingMethod.objects.get(pk=1),
            }
        except (
            Company.DoesNotExist,
            CultivationType.DoesNotExist,
            LandPeriod.DoesNotExist,
            SamplingMethod.DoesNotExist,
        ) as error:
            raise CommandError(
                "代表圃場データの作成に必要な参照マスタが不足しています。"
                "company、cultivationtype、land_period、samplingmethod のfixtureを"
                "先に読み込んでください。"
            ) from error
        references["owner"] = _get_user_by_role(
            role=UserAttribute.Role.OWNER,
            organization=references["company"].name,
            role_label="圃場オーナー",
        )
        references["sampling_staff"] = _get_user_by_role(
            role=UserAttribute.Role.STAFF,
            organization=None,
            role_label="採土スタッフ",
        )
        return references

    @staticmethod
    def _build_crop_id_by_name() -> dict[str, int]:
        crop_names = sorted(
            {
                crop_name
                for crops in PREFECTURE_REPRESENTATIVE_CROPS.values()
                for crop_name in crops
            }
        )
        return {
            crop_name: crop_id
            for crop_id, crop_name in enumerate(crop_names, start=1000)
        }

    @staticmethod
    def _create_crops(crop_id_by_name: dict[str, int]) -> dict[str, Crop]:
        crops = {}
        for crop_name, crop_id in sorted(
            crop_id_by_name.items(), key=lambda item: item[1]
        ):
            crop, _ = Crop.objects.update_or_create(
                pk=crop_id,
                defaults={
                    "name": crop_name,
                    "remark": SOURCE_NOTE,
                },
            )
            crops[crop_name] = crop
        return crops

    @staticmethod
    def _create_lands(
        cities_by_prefecture: dict[str, JmaCity],
        references: dict[str, object],
    ) -> dict[int, Land]:
        lands = {}
        for prefecture_index, prefecture_name in JAPAN_MAP_PREFECTURES:
            city = cities_by_prefecture[prefecture_name]
            for crop_index, crop_name in enumerate(
                PREFECTURE_REPRESENTATIVE_CROPS[prefecture_name], start=1
            ):
                land_id = _build_prefecture_record_id(prefecture_index, crop_index)
                land, _ = Land.objects.update_or_create(
                    pk=land_id,
                    defaults={
                        "name": (
                            f"{prefecture_name}代表圃場{crop_index:02d}"
                            f"（{crop_name}）"
                        ),
                        "center": _get_prefecture_center(prefecture_index),
                        "jma_city": city,
                        "area": 10.0 + crop_index,
                        "cultivation_type": references["cultivation_type"],
                        "company": references["company"],
                        "owner": references["owner"],
                        "remark": (
                            f"prefecture_code={prefecture_index:02d}; "
                            f"representative_crop_rank={crop_index}; "
                            f"source={SOURCE_NOTE}"
                        ),
                    },
                )
                lands[land_id] = land
        return lands

    @staticmethod
    def _create_land_ledgers(
        crops: dict[str, Crop],
        lands: dict[int, Land],
        references: dict[str, object],
    ) -> None:
        for prefecture_index, prefecture_name in JAPAN_MAP_PREFECTURES:
            for crop_index, crop_name in enumerate(
                PREFECTURE_REPRESENTATIVE_CROPS[prefecture_name], start=1
            ):
                record_id = _build_prefecture_record_id(prefecture_index, crop_index)
                LandLedger.objects.update_or_create(
                    pk=record_id,
                    defaults={
                        "sampling_date": "2026-03-03",
                        "analysis_request_date": "2026-03-13",
                        "reporting_date": "2026-03-20",
                        "analytical_agency": references["analytical_agency"],
                        "crop": crops[crop_name],
                        "land": lands[record_id],
                        "land_period": references["land_period"],
                        "sampling_method": references["sampling_method"],
                        "sampling_staff": references["sampling_staff"],
                    },
                )


def _build_prefecture_record_id(prefecture_index: int, crop_index: int) -> int:
    return 1000 + (prefecture_index - 1) * 3 + crop_index


def _get_user_by_role(role: str, organization: str | None, role_label: str):
    user_attributes = UserAttribute.objects.select_related("user").filter(role=role)
    if organization is not None:
        user_attributes = user_attributes.filter(organization=organization)

    user_attribute = user_attributes.order_by("id").first()
    if user_attribute is None:
        condition = f"organization={organization}, role={role}"
        raise CommandError(
            f"代表圃場データの作成に必要な{role_label}が見つかりません: {condition}"
        )
    return user_attribute.user


def _get_prefecture_center(prefecture_index: int) -> str:
    latitude = 45.0 - prefecture_index * 0.45
    longitude = 141.0 - prefecture_index * 0.35
    return f"{latitude:.4f},{longitude:.4f}"
