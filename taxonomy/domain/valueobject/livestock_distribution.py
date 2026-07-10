from dataclasses import dataclass


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


PREFECTURE_CODES = (
    (1, "北海道"),
    (2, "青森"),
    (3, "岩手"),
    (4, "宮城"),
    (5, "秋田"),
    (6, "山形"),
    (7, "福島"),
    (8, "茨城"),
    (9, "栃木"),
    (10, "群馬"),
    (11, "埼玉"),
    (12, "千葉"),
    (13, "東京"),
    (14, "神奈川"),
    (15, "新潟"),
    (16, "富山"),
    (17, "石川"),
    (18, "福井"),
    (19, "山梨"),
    (20, "長野"),
    (21, "岐阜"),
    (22, "静岡"),
    (23, "愛知"),
    (24, "三重"),
    (25, "滋賀"),
    (26, "京都"),
    (27, "大阪"),
    (28, "兵庫"),
    (29, "奈良"),
    (30, "和歌山"),
    (31, "鳥取"),
    (32, "島根"),
    (33, "岡山"),
    (34, "広島"),
    (35, "山口"),
    (36, "徳島"),
    (37, "香川"),
    (38, "愛媛"),
    (39, "高知"),
    (40, "福岡"),
    (41, "佐賀"),
    (42, "長崎"),
    (43, "熊本"),
    (44, "大分"),
    (45, "宮崎"),
    (46, "鹿児島"),
    (47, "沖縄"),
)


def _build_prefecture_distribution(
    rows: dict[str, tuple[int | None, int | None]],
) -> tuple[LivestockPrefectureDistribution, ...]:
    return tuple(
        LivestockPrefectureDistribution(
            code=code,
            prefecture=prefecture,
            households=rows[prefecture][0],
            birds_thousand=rows[prefecture][1],
        )
        for code, prefecture in PREFECTURE_CODES
    )


def build_livestock_distribution_dashboard() -> LivestockDistributionDashboard:
    """
    e-Stat畜産統計調査の採卵鶏・ブロイラー分布を返します。

    令和6年畜産統計のExcelを2026-07-11に取得し、秘匿値はNoneとして保持します。
    """
    layer_rows = {
        "北海道": (56, 5692),
        "青森": (24, 6540),
        "岩手": (23, 5097),
        "宮城": (33, 3964),
        "秋田": (15, 2374),
        "山形": (13, 427),
        "福島": (37, 5220),
        "茨城": (83, 12310),
        "栃木": (43, 6177),
        "群馬": (46, 9765),
        "埼玉": (63, 3651),
        "千葉": (90, 14173),
        "東京": (15, 69),
        "神奈川": (38, 1041),
        "新潟": (42, 4695),
        "富山": (14, 719),
        "石川": (6, 690),
        "福井": (12, 740),
        "山梨": (17, 505),
        "長野": (17, 690),
        "岐阜": (57, 5831),
        "静岡": (47, 4794),
        "愛知": (113, 8109),
        "三重": (63, 5749),
        "滋賀": (15, 242),
        "京都": (25, 1515),
        "大阪": (12, 49),
        "兵庫": (44, 5677),
        "奈良": (23, 284),
        "和歌山": (18, 265),
        "鳥取": (8, 242),
        "島根": (14, 934),
        "岡山": (48, 10036),
        "広島": (41, 9260),
        "山口": (13, 1655),
        "徳島": (14, 831),
        "香川": (36, 5059),
        "愛媛": (35, 2148),
        "高知": (10, 275),
        "福岡": (55, 2874),
        "佐賀": (24, 251),
        "長崎": (51, 1826),
        "熊本": (38, 2481),
        "大分": (15, 914),
        "宮崎": (53, 3194),
        "鹿児島": (101, 10302),
        "沖縄": (35, 1440),
    }
    broiler_rows = {
        "北海道": (8, 5531),
        "青森": (59, 7639),
        "岩手": (301, 23604),
        "宮城": (37, 1990),
        "秋田": (None, None),
        "山形": (13, 542),
        "福島": (31, 751),
        "茨城": (36, 1350),
        "栃木": (8, None),
        "群馬": (26, 1587),
        "埼玉": (1, None),
        "千葉": (24, 1935),
        "東京": (None, None),
        "神奈川": (None, None),
        "新潟": (10, 1201),
        "富山": (None, None),
        "石川": (None, None),
        "福井": (3, 91),
        "山梨": (8, 392),
        "長野": (18, 696),
        "岐阜": (11, 939),
        "静岡": (18, 947),
        "愛知": (12, 962),
        "三重": (8, 662),
        "滋賀": (2, None),
        "京都": (11, 535),
        "大阪": (None, None),
        "兵庫": (32, 2412),
        "奈良": (1, None),
        "和歌山": (16, 231),
        "鳥取": (11, 3151),
        "島根": (4, 377),
        "岡山": (18, 2840),
        "広島": (8, 647),
        "山口": (22, 1497),
        "徳島": (134, 3855),
        "香川": (30, 2119),
        "愛媛": (22, 957),
        "高知": (9, 397),
        "福岡": (30, 1168),
        "佐賀": (62, 3929),
        "長崎": (48, 3297),
        "熊本": (56, 3746),
        "大分": (42, 1782),
        "宮崎": (442, 28155),
        "鹿児島": (402, 32003),
        "沖縄": (15, 624),
    }

    return LivestockDistributionDashboard(
        source_name="e-Stat / 農林水産省 畜産統計調査",
        source_stat_code="00500222",
        survey_year=2024,
        retrieved_at="2026-07-11",
        source_url=(
            "https://www.e-stat.go.jp/stat-search/files"
            "?layout=datalist&lid=000001447249&page=1"
        ),
        note="令和6年2月1日現在。単位は千羽。e-Statの秘匿値 x と該当なし - は推計せず秘匿・該当なしとして表示します。",
        categories=(
            LivestockCategoryDistribution(
                key="layers",
                label="採卵鶏",
                table_number="4",
                table_title="飼養戸数・羽数（全国農業地域・都道府県別）",
                national_households=1700,
                national_birds_thousand=170776,
                prefectures=_build_prefecture_distribution(layer_rows),
            ),
            LivestockCategoryDistribution(
                key="broilers",
                label="ブロイラー",
                table_number="5",
                table_title="飼養戸数・羽数（全国農業地域・都道府県別）",
                national_households=2050,
                national_birds_thousand=144859,
                prefectures=_build_prefecture_distribution(broiler_rows),
            ),
        ),
    )
