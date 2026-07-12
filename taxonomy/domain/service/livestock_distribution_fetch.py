import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO

from django.core.files.base import ContentFile
from django.db import transaction

from taxonomy.domain.dataprovider.estat import EstatApiClient
from taxonomy.domain.valueobject.livestock_distribution import (
    LivestockDistributionCsvRow,
    load_livestock_distribution_rows,
)
from taxonomy.models import LivestockDistributionDataset

SOURCE_STAT_CODE = "00500222"
SOURCE_NAME = "e-Stat / 農林水産省 畜産統計調査"
SOURCE_URL = (
    "https://www.e-stat.go.jp/stat-search/files"
    "?toukei=00500222&tstat=000001015614&tclass1=000001020206"
)
SURVEY_YEAR = 2024
RETRIEVED_ON = date.today
NOTE = (
    "令和6年2月1日現在。単位は千羽。e-Statの秘匿値 x と"
    "該当なし - は推計せず秘匿・該当なしとして表示します。"
)


class LivestockDistributionFetchError(Exception):
    """
    畜産統計の取得・変換・保存でユーザーに表示する例外です。
    """


class LivestockDistributionApiError(LivestockDistributionFetchError):
    """
    e-Stat APIへの接続またはレスポンス取得に失敗したことを表します。
    """


class LivestockDistributionParseError(LivestockDistributionFetchError):
    """
    e-Stat APIレスポンスを畜産統計CSV形式へ変換できないことを表します。
    """


class LivestockDistributionSaveError(LivestockDistributionFetchError):
    """
    変換済みの畜産統計CSVをDBへ保存できないことを表します。
    """


@dataclass(frozen=True)
class LivestockDistributionTableDefinition:
    """
    取得対象の畜産統計表定義。

    Attributes:
        category_key: 画面切替に使う分類キー。
        category_label: 統計分類名。
        table_number: e-Statの表番号。
        table_title: 統計表名。
        stats_data_id: e-Stat 統計表表示ID。
    """

    category_key: str
    category_label: str
    table_number: str
    table_title: str
    stats_data_id: str


@dataclass(frozen=True)
class LivestockDistributionFetchResult:
    """
    畜産統計取得ボタンの実行結果。

    Attributes:
        dataset: 保存したデータセット。
        row_count: CSVへ変換した行数。
    """

    dataset: LivestockDistributionDataset
    row_count: int


TABLE_DEFINITIONS = (
    LivestockDistributionTableDefinition(
        category_key="layers",
        category_label="採卵鶏",
        table_number="4",
        table_title="採卵鶏の飼養戸数・羽数",
        stats_data_id="0004041877",
    ),
    LivestockDistributionTableDefinition(
        category_key="broilers",
        category_label="ブロイラー",
        table_number="5",
        table_title="ブロイラーの飼養戸数・羽数",
        stats_data_id="0004041880",
    ),
)

PREFECTURE_CODES = {
    "北海道": 1,
    "青森県": 2,
    "岩手県": 3,
    "宮城県": 4,
    "秋田県": 5,
    "山形県": 6,
    "福島県": 7,
    "茨城県": 8,
    "栃木県": 9,
    "群馬県": 10,
    "埼玉県": 11,
    "千葉県": 12,
    "東京都": 13,
    "神奈川県": 14,
    "新潟県": 15,
    "富山県": 16,
    "石川県": 17,
    "福井県": 18,
    "山梨県": 19,
    "長野県": 20,
    "岐阜県": 21,
    "静岡県": 22,
    "愛知県": 23,
    "三重県": 24,
    "滋賀県": 25,
    "京都府": 26,
    "大阪府": 27,
    "兵庫県": 28,
    "奈良県": 29,
    "和歌山県": 30,
    "鳥取県": 31,
    "島根県": 32,
    "岡山県": 33,
    "広島県": 34,
    "山口県": 35,
    "徳島県": 36,
    "香川県": 37,
    "愛媛県": 38,
    "高知県": 39,
    "福岡県": 40,
    "佐賀県": 41,
    "長崎県": 42,
    "熊本県": 43,
    "大分県": 44,
    "宮崎県": 45,
    "鹿児島県": 46,
    "沖縄県": 47,
}


class LivestockDistributionFetchService:
    """
    e-Stat畜産統計APIから鶏の地域別飼養分布を取得して保存するServiceです。
    """

    @classmethod
    def fetch_and_save(cls, app_id: str) -> LivestockDistributionFetchResult:
        client = EstatApiClient(app_id)
        rows = []
        for definition in TABLE_DEFINITIONS:
            response = cls._fetch_stats_data(client, definition)
            rows.extend(cls._parse_rows(definition, response))

        csv_text = cls._build_csv_text(rows)
        cls._validate_csv(csv_text)
        dataset = cls._save_dataset(csv_text)
        return LivestockDistributionFetchResult(dataset=dataset, row_count=len(rows))

    @staticmethod
    def _fetch_stats_data(
        client: EstatApiClient,
        definition: LivestockDistributionTableDefinition,
    ) -> dict:
        try:
            return client.get_stats_data(definition.stats_data_id)
        except Exception as error:
            message = f"{definition.category_label}のe-Stat API取得に失敗しました。"
            raise LivestockDistributionApiError(message) from error

    @classmethod
    def _parse_rows(
        cls,
        definition: LivestockDistributionTableDefinition,
        response: dict,
    ) -> list[LivestockDistributionCsvRow]:
        try:
            statistical_data = response["GET_STATS_DATA"]["STATISTICAL_DATA"]
            class_labels = cls._build_class_labels(statistical_data["CLASS_INF"])
            values = cls._as_list(statistical_data["DATA_INF"]["VALUE"])
            area_values = {}
            for value in values:
                area_name = class_labels["area"].get(value["@area"], value["@area"])
                prefecture_code = cls._prefecture_code(area_name)
                if prefecture_code is None:
                    continue

                tab_name = class_labels["tab"].get(value["@tab"], value["@tab"])
                item = area_values.setdefault(
                    prefecture_code,
                    {
                        "prefecture": cls._prefecture_name(area_name),
                        "households": None,
                        "birds_thousand": None,
                    },
                )
                if "戸数" in tab_name:
                    item["households"] = cls._parse_optional_int(value.get("$", ""))
                elif "羽数" in tab_name:
                    item["birds_thousand"] = cls._parse_optional_int(value.get("$", ""))

            rows = []
            for prefecture_code, item in sorted(area_values.items()):
                rows.append(
                    LivestockDistributionCsvRow(
                        category_key=definition.category_key,
                        category_label=definition.category_label,
                        table_number=definition.table_number,
                        table_title=definition.table_title,
                        prefecture_code=prefecture_code,
                        prefecture=item["prefecture"],
                        households=item["households"],
                        birds_thousand=item["birds_thousand"],
                    )
                )
        except (KeyError, TypeError, ValueError) as error:
            message = (
                f"{definition.category_label}のe-Statレスポンス解析に失敗しました。"
            )
            raise LivestockDistributionParseError(message) from error

        if len(rows) != 48:
            message = (
                f"{definition.category_label}の都道府県データ数が不足しています。"
                f"取得件数: {len(rows)}"
            )
            raise LivestockDistributionParseError(message)
        return rows

    @classmethod
    def _build_class_labels(cls, class_inf: dict) -> dict[str, dict[str, str]]:
        labels = {}
        class_objects = cls._as_list(class_inf["CLASS_OBJ"])
        for class_object in class_objects:
            class_id = class_object["@id"]
            labels[class_id] = {}
            for class_item in cls._as_list(class_object["CLASS"]):
                labels[class_id][class_item["@code"]] = class_item["@name"]
        return labels

    @staticmethod
    def _as_list(value: object) -> list:
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _prefecture_code(area_name: str) -> int | None:
        prefecture_name = LivestockDistributionFetchService._prefecture_name(area_name)
        if prefecture_name == "全国":
            return 0
        return PREFECTURE_CODES.get(prefecture_name)

    @staticmethod
    def _prefecture_name(area_name: str) -> str:
        return area_name.split("_")[-1]

    @staticmethod
    def _parse_optional_int(value: object) -> int | None:
        text = str(value).replace(",", "").strip()
        if text in {"", "-", "x", "X", "..."}:
            return None
        return int(float(text))

    @staticmethod
    def _build_csv_text(rows: list[LivestockDistributionCsvRow]) -> str:
        output = StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "category_key",
                "category_label",
                "table_number",
                "table_title",
                "prefecture_code",
                "prefecture",
                "households",
                "birds_thousand",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.category_key,
                    row.category_label,
                    row.table_number,
                    row.table_title,
                    row.prefecture_code,
                    row.prefecture,
                    row.households or "",
                    row.birds_thousand or "",
                ]
            )
        return output.getvalue()

    @staticmethod
    def _validate_csv(csv_text: str) -> None:
        try:
            rows = load_livestock_distribution_rows(StringIO(csv_text))
        except (KeyError, ValueError) as error:
            raise LivestockDistributionParseError(
                "e-Statレスポンスを畜産統計CSV形式へ変換できませんでした。"
            ) from error
        if not rows:
            raise LivestockDistributionParseError(
                "e-Statレスポンスに畜産統計データがありません。"
            )

    @staticmethod
    @transaction.atomic
    def _save_dataset(csv_text: str) -> LivestockDistributionDataset:
        try:
            retrieved_on = RETRIEVED_ON()
            dataset = LivestockDistributionDataset(
                title="令和6年畜産統計",
                source_name=SOURCE_NAME,
                source_stat_code=SOURCE_STAT_CODE,
                survey_year=SURVEY_YEAR,
                retrieved_at=retrieved_on,
                source_url=SOURCE_URL,
                note=NOTE,
                is_active=True,
            )
            dataset.csv_file.save(
                f"livestock_distribution_{SURVEY_YEAR}_{retrieved_on.isoformat()}.csv",
                ContentFile(csv_text.encode("utf-8")),
                save=False,
            )
            dataset.save()
        except Exception as error:
            raise LivestockDistributionSaveError(
                "畜産統計CSVのDB保存に失敗しました。"
            ) from error
        return dataset
