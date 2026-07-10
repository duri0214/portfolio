import csv
from dataclasses import dataclass
from datetime import date
from io import TextIOBase


@dataclass(frozen=True)
class LivestockPrefectureDistribution:
    """
    e-Stat畜産統計の都道府県別飼養データ。

    Attributes:
        code: japan-map-jsで使う1から47の都道府県コード。
        prefecture: 都道府県名。
        households: 飼養戸数。秘匿または未調査の場合はNone。
        birds_thousand: 飼養羽数（千羽）。秘匿または未調査の場合はNone。
    """

    code: int
    prefecture: str
    households: int | None
    birds_thousand: int | None

    @property
    def birds_label(self) -> str:
        if self.birds_thousand is None:
            return "秘匿・該当なし"
        return f"{self.birds_thousand:,}千羽"

    @property
    def households_label(self) -> str:
        if self.households is None:
            return "秘匿・該当なし"
        return f"{self.households:,}戸"


@dataclass(frozen=True)
class LivestockCategoryDistribution:
    """
    e-Stat畜産統計の統計分類別飼養データ。

    Attributes:
        key: 画面切替に使う分類キー。
        label: 統計分類名。
        table_number: e-Statの表番号。
        table_title: 統計表名。
        national_households: 全国の飼養戸数。
        national_birds_thousand: 全国の飼養羽数（千羽）。
        prefectures: 都道府県別の飼養データ。
    """

    key: str
    label: str
    table_number: str
    table_title: str
    national_households: int
    national_birds_thousand: int
    prefectures: tuple[LivestockPrefectureDistribution, ...]

    @property
    def national_birds_label(self) -> str:
        return f"{self.national_birds_thousand:,}千羽"

    @property
    def national_households_label(self) -> str:
        return f"{self.national_households:,}戸"

    def to_summary_payload(self) -> dict[str, int | str]:
        return {
            "key": self.key,
            "label": self.label,
            "tableNumber": self.table_number,
            "tableTitle": self.table_title,
            "nationalHouseholds": self.national_households,
            "nationalHouseholdsLabel": self.national_households_label,
            "nationalBirdsThousand": self.national_birds_thousand,
            "nationalBirdsLabel": self.national_birds_label,
        }

    def to_map_payload(self) -> list[dict[str, int | str | None]]:
        return [
            {
                "code": prefecture.code,
                "name": prefecture.prefecture,
                "households": prefecture.households,
                "householdsLabel": prefecture.households_label,
                "birdsThousand": prefecture.birds_thousand,
                "birdsLabel": prefecture.birds_label,
            }
            for prefecture in self.prefectures
        ]


@dataclass(frozen=True)
class LivestockDistributionDashboard:
    """
    Taxonomyトップで表示する畜産統計ダッシュボード。

    Attributes:
        source_name: データ源名。
        source_stat_code: 政府統計コード。
        survey_year: 対象年。
        retrieved_at: ローカル取得日。
        source_url: e-Statの統計表一覧URL。
        note: 表示上の注意事項。
        categories: 採卵鶏・ブロイラーの統計分類別データ。
    """

    source_name: str
    source_stat_code: str
    survey_year: int
    retrieved_at: str
    source_url: str
    note: str
    categories: tuple[LivestockCategoryDistribution, ...]

    @property
    def total_birds_thousand(self) -> int:
        return sum(category.national_birds_thousand for category in self.categories)

    def to_payload(self) -> dict[str, object]:
        total_birds = self.total_birds_thousand
        categories = []
        maps = {}
        for category in self.categories:
            share = round(category.national_birds_thousand / total_birds * 100, 1)
            summary = category.to_summary_payload()
            summary["share"] = share
            categories.append(summary)
            maps[category.key] = category.to_map_payload()

        return {
            "sourceName": self.source_name,
            "sourceStatCode": self.source_stat_code,
            "surveyYear": self.survey_year,
            "retrievedAt": self.retrieved_at,
            "sourceUrl": self.source_url,
            "note": self.note,
            "categories": categories,
            "maps": maps,
        }


@dataclass(frozen=True)
class LivestockDistributionSource:
    """
    e-Stat畜産統計CSVの出典メタ情報。

    Attributes:
        source_name: データ源名。
        source_stat_code: 政府統計コード。
        survey_year: 対象年。
        retrieved_at: ローカル取得日。
        source_url: e-Statの統計表一覧URL。
        note: 表示上の注意事項。
    """

    source_name: str
    source_stat_code: str
    survey_year: int
    retrieved_at: date
    source_url: str
    note: str


@dataclass(frozen=True)
class LivestockDistributionCsvRow:
    """
    CSVに切り出したe-Stat畜産統計の1行。

    Attributes:
        category_key: 統計分類キー。
        category_label: 統計分類名。
        table_number: e-Statの表番号。
        table_title: 統計表名。
        prefecture_code: japan-map-jsで使う1から47の都道府県コード。
        prefecture: 都道府県名。
        households: 飼養戸数。秘匿または該当なしの場合はNone。
        birds_thousand: 飼養羽数（千羽）。秘匿または該当なしの場合はNone。
    """

    category_key: str
    category_label: str
    table_number: str
    table_title: str
    prefecture_code: int
    prefecture: str
    households: int | None
    birds_thousand: int | None


def build_livestock_distribution_dashboard_from_rows(
    source: LivestockDistributionSource,
    rows: list[LivestockDistributionCsvRow],
) -> LivestockDistributionDashboard:
    """
    登録済み畜産統計CSVの行データからダッシュボードを組み立てます。

    秘匿値はCSV上で空欄にしておき、推計せずNoneとして保持します。
    """
    categories = _build_categories(rows)
    return LivestockDistributionDashboard(
        source_name=source.source_name,
        source_stat_code=source.source_stat_code,
        survey_year=source.survey_year,
        retrieved_at=source.retrieved_at.isoformat(),
        source_url=source.source_url,
        note=source.note,
        categories=categories,
    )


def load_livestock_distribution_rows(
    csv_file: TextIOBase,
) -> list[LivestockDistributionCsvRow]:
    """
    畜産統計CSVのファイルオブジェクトから行データを読み込みます。
    """
    reader = csv.DictReader(csv_file)
    return [
        LivestockDistributionCsvRow(
            category_key=row["category_key"],
            category_label=row["category_label"],
            table_number=row["table_number"],
            table_title=row["table_title"],
            prefecture_code=int(row["prefecture_code"]),
            prefecture=row["prefecture"],
            households=_parse_optional_int(row["households"]),
            birds_thousand=_parse_optional_int(row["birds_thousand"]),
        )
        for row in reader
    ]


def _build_categories(
    rows: list[LivestockDistributionCsvRow],
) -> tuple[LivestockCategoryDistribution, ...]:
    categories = []
    category_keys = []
    for row in rows:
        if row.category_key not in category_keys:
            category_keys.append(row.category_key)

    for category_key in category_keys:
        category_rows = [row for row in rows if row.category_key == category_key]
        national_row = next(row for row in category_rows if row.prefecture_code == 0)
        prefecture_rows = [
            row for row in category_rows if 1 <= row.prefecture_code <= 47
        ]
        categories.append(
            LivestockCategoryDistribution(
                key=national_row.category_key,
                label=national_row.category_label,
                table_number=national_row.table_number,
                table_title=national_row.table_title,
                national_households=national_row.households or 0,
                national_birds_thousand=national_row.birds_thousand or 0,
                prefectures=tuple(
                    LivestockPrefectureDistribution(
                        code=row.prefecture_code,
                        prefecture=row.prefecture,
                        households=row.households,
                        birds_thousand=row.birds_thousand,
                    )
                    for row in prefecture_rows
                ),
            )
        )
    return tuple(categories)


def _parse_optional_int(value: str) -> int | None:
    stripped_value = value.strip()
    if not stripped_value:
        return None
    return int(stripped_value)
