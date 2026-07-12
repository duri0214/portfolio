import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO

from taxonomy.domain.dataprovider.estat import EstatApiClient
from taxonomy.domain.repository.livestock_distribution import (
    LivestockDistributionDatasetRepository,
)
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
CURRENT_DATE = date.today
MIN_SURVEY_YEAR = 1960
LIVESTOCK_SURVEY_REFERENCE_MONTH = 2
LIVESTOCK_SURVEY_REFERENCE_DAY = 1
LIVESTOCK_SURVEY_REFERENCE_DESCRIPTION = "畜産統計調査の調査基準日"


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
    """

    category_key: str
    category_label: str
    table_number: str
    table_title: str


@dataclass(frozen=True)
class LivestockDistributionFetchResult:
    """
    畜産統計取得ボタンの実行結果。

    Attributes:
        dataset: 保存したデータセット。
        row_count: CSVへ変換した行数。
        created: 新規作成した場合はTrue、既存データを更新した場合はFalse。
    """

    dataset: LivestockDistributionDataset
    row_count: int
    created: bool


TABLE_DEFINITIONS = (
    LivestockDistributionTableDefinition(
        category_key="layers",
        category_label="採卵鶏",
        table_number="4",
        table_title="採卵鶏の飼養戸数・羽数",
    ),
    LivestockDistributionTableDefinition(
        category_key="broilers",
        category_label="ブロイラー",
        table_number="5",
        table_title="ブロイラーの飼養戸数・羽数",
    ),
)

PREFECTURES = (
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
)
PREFECTURE_CODES = {
    prefecture: code for code, prefecture in enumerate(PREFECTURES, start=1)
}
PREFECTURE_NAMES_BY_SHORT_NAME = {
    prefecture.removesuffix("都").removesuffix("府").removesuffix("県"): prefecture
    for prefecture in PREFECTURES
}


class LivestockDistributionFetchService:
    """
    e-Stat畜産統計APIから鶏の地域別飼養分布を取得して保存するServiceです。
    """

    @classmethod
    def fetch_and_save(
        cls, app_id: str, survey_year: int
    ) -> LivestockDistributionFetchResult:
        client = EstatApiClient(app_id)
        rows = []
        for definition in TABLE_DEFINITIONS:
            stats_data_id = cls._find_stats_data_id(client, definition, survey_year)
            response = cls._fetch_stats_data(client, definition, stats_data_id)
            rows.extend(cls._parse_rows(definition, response))

        csv_text = cls._build_csv_text(rows)
        cls._validate_csv(csv_text)
        dataset, created = cls._save_dataset(csv_text, survey_year)
        return LivestockDistributionFetchResult(
            dataset=dataset,
            row_count=len(rows),
            created=created,
        )

    @classmethod
    def validate_survey_year(cls, survey_year: int) -> None:
        """
        取得対象年として扱える西暦か検証します。
        """
        if survey_year < MIN_SURVEY_YEAR or survey_year > CURRENT_DATE().year:
            raise LivestockDistributionFetchError(
                "取得年度は1960年から今年までの西暦で指定してください。"
            )

    @classmethod
    def _find_stats_data_id(
        cls,
        client: EstatApiClient,
        definition: LivestockDistributionTableDefinition,
        survey_year: int,
    ) -> str:
        cls.validate_survey_year(survey_year)
        try:
            response = client.get_stats_list(
                {
                    "statsCode": SOURCE_STAT_CODE,
                    "surveyYears": f"{survey_year}0",
                    "searchKind": "3",
                    "searchWord": f"{definition.category_label} 飼養戸数 羽数",
                }
            )
            table_infos = cls._as_list(
                response["GET_STATS_LIST"]["DATALIST_INF"].get("TABLE_INF", [])
            )
            for table_info in table_infos:
                table_text = cls._table_info_text(table_info)
                if cls._matches_table_definition(table_text, definition, survey_year):
                    return table_info["@id"]
        except Exception as error:
            message = (
                f"{survey_year}年{definition.category_label}の"
                "e-Stat統計表検索に失敗しました。"
            )
            raise LivestockDistributionApiError(message) from error

        message = (
            f"{survey_year}年{definition.category_label}の"
            "飼養戸数・羽数統計表が見つかりませんでした。"
        )
        raise LivestockDistributionApiError(message)

    @staticmethod
    def _fetch_stats_data(
        client: EstatApiClient,
        definition: LivestockDistributionTableDefinition,
        stats_data_id: str,
    ) -> dict:
        try:
            return client.get_stats_data(stats_data_id)
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
            area_class_id = cls._find_area_class_id(class_labels)
            item_class_id = cls._find_livestock_item_class_id(class_labels)
            values = cls._as_list(statistical_data["DATA_INF"]["VALUE"])
            area_values = {}
            for value in values:
                area_code = value[f"@{area_class_id}"]
                item_code = value[f"@{item_class_id}"]
                area_name = class_labels[area_class_id].get(area_code, area_code)
                prefecture_code = cls._prefecture_code(area_name)
                if prefecture_code is None:
                    continue

                item_name = class_labels[item_class_id].get(item_code, item_code)
                item = area_values.setdefault(
                    prefecture_code,
                    {
                        "prefecture": cls._prefecture_name(area_name),
                        "households": None,
                        "birds_thousand": None,
                    },
                )
                if cls._is_households_item(item_name):
                    item["households"] = cls._parse_optional_int(value.get("$", ""))
                elif cls._is_birds_item(item_name):
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

    @classmethod
    def _find_area_class_id(cls, class_labels: dict[str, dict[str, str]]) -> str:
        for class_id, labels in class_labels.items():
            if any(
                cls._prefecture_code(label) is not None for label in labels.values()
            ):
                return class_id
        raise ValueError("e-Statレスポンスに地域分類がありません。")

    @classmethod
    def _find_livestock_item_class_id(
        cls, class_labels: dict[str, dict[str, str]]
    ) -> str:
        for class_id, labels in class_labels.items():
            has_households = any(
                cls._is_households_item(label) for label in labels.values()
            )
            has_birds = any(cls._is_birds_item(label) for label in labels.values())
            if has_households and has_birds:
                return class_id
        raise ValueError("e-Statレスポンスに飼養戸数・羽数分類がありません。")

    @staticmethod
    def _is_households_item(item_name: str) -> bool:
        if "対前年比" in item_name or "種鶏" in item_name:
            return False
        return (
            item_name == "飼養戸数"
            or item_name.endswith("飼養戸数")
            or "飼養戸数_採卵鶏" in item_name
        )

    @staticmethod
    def _is_birds_item(item_name: str) -> bool:
        if "対前年比" in item_name or "１戸当たり" in item_name:
            return False
        return "飼養羽数_計" in item_name or item_name.endswith("飼養羽数")

    @staticmethod
    def _as_list(value: object) -> list:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @classmethod
    def _matches_table_definition(
        cls,
        table_text: str,
        definition: LivestockDistributionTableDefinition,
        survey_year: int,
    ) -> bool:
        normalized_text = cls._normalize_table_text(table_text)
        era_year = cls._japanese_era_year(survey_year)
        return (
            definition.category_label in normalized_text
            and era_year in normalized_text
            and "飼養戸数" in normalized_text
            and "羽数" in normalized_text
            and "都道府県" in normalized_text
        )

    @classmethod
    def _table_info_text(cls, value: object) -> str:
        if isinstance(value, dict):
            return " ".join(cls._table_info_text(item) for item in value.values())
        if isinstance(value, list):
            return " ".join(cls._table_info_text(item) for item in value)
        return str(value)

    @staticmethod
    def _normalize_table_text(text: str) -> str:
        return text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

    @staticmethod
    def _japanese_era_year(survey_year: int) -> str:
        if survey_year >= 2019:
            era_year = survey_year - 2018
            return "令和元年" if era_year == 1 else f"令和{era_year}年"
        if survey_year >= 1989:
            era_year = survey_year - 1988
            return "平成元年" if era_year == 1 else f"平成{era_year}年"
        return f"{survey_year}年"

    @classmethod
    def _note(cls, survey_year: int) -> str:
        era_year = cls._japanese_era_year(survey_year)
        reference_date = (
            f"{era_year}{LIVESTOCK_SURVEY_REFERENCE_MONTH}月"
            f"{LIVESTOCK_SURVEY_REFERENCE_DAY}日現在"
        )
        return (
            f"{reference_date}（{LIVESTOCK_SURVEY_REFERENCE_DESCRIPTION}）。"
            "単位は千羽。e-Statの秘匿値 x と"
            "該当なし - は推計せず秘匿・該当なしとして表示します。"
        )

    @staticmethod
    def _prefecture_code(area_name: str) -> int | None:
        prefecture_name = LivestockDistributionFetchService._prefecture_name(area_name)
        if prefecture_name == "全国":
            return 0
        return PREFECTURE_CODES.get(prefecture_name)

    @staticmethod
    def _prefecture_name(area_name: str) -> str:
        name = area_name.split("_")[-1]
        return PREFECTURE_NAMES_BY_SHORT_NAME.get(name, name)

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
    def _save_dataset(
        csv_text: str, survey_year: int
    ) -> tuple[LivestockDistributionDataset, bool]:
        try:
            retrieved_on = CURRENT_DATE()
            era_year = LivestockDistributionFetchService._japanese_era_year(survey_year)
            return LivestockDistributionDatasetRepository.save_fetched_dataset(
                csv_text=csv_text,
                title=f"{era_year}畜産統計",
                source_name=SOURCE_NAME,
                source_stat_code=SOURCE_STAT_CODE,
                survey_year=survey_year,
                retrieved_at=retrieved_on,
                source_url=SOURCE_URL,
                note=LivestockDistributionFetchService._note(survey_year),
            )
        except Exception as error:
            raise LivestockDistributionSaveError(
                "畜産統計CSVのDB保存に失敗しました。"
            ) from error
