import csv
from io import StringIO

from shopping.domain.dataprovider.public_dataset import PublicDatasetClient
from shopping.domain.repository.store_planning import StorePlanningDataSourceRepository
from shopping.domain.valueobject.store_planning import StorePlanningDataSource


class StorePlanningDataSourceService:
    """出店計画で使う外部データソースのメタ情報を取得して保存する。"""

    ESTAT_POPULATION_SOURCE_URL = (
        "https://www.e-stat.go.jp/stat-search/files"
        "?cycle=0&cycle_facet=tclass1%3Acycle&layout=datalist&page=1"
        "&tclass1=000001136472&tclass2=000001159886&tclass3val=0"
        "&toukei=00200521&tstat=000001136464"
    )
    ESTAT_POPULATION_CSV_URL = (
        "https://www.e-stat.go.jp/stat-search/file-download"
        "?statInfId=000032163275&fileKind=1"
    )
    ESTAT_POPULATION_STAT_INF_ID = "000032163275"
    ESTAT_POPULATION_RESOURCE_ID = "000009048041"
    ESTAT_POPULATION_TABLE_NAME = (
        "男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等"
    )
    TARGET_CITY_CODE = "13121"
    TARGET_TOWN_CODE = "073002"
    TARGET_AREA_NAME = "東京都足立区東保木間二丁目"
    AGE_GROUPS = [
        ("0代", list(range(13, 15))),
        ("10代", list(range(15, 17))),
        ("20代", list(range(17, 19))),
        ("30代", list(range(19, 21))),
        ("40代", list(range(21, 23))),
        ("50代", list(range(23, 25))),
        ("60代", list(range(25, 27))),
        ("70代", list(range(27, 29))),
        ("80代", list(range(29, 31))),
        ("90代", list(range(31, 33))),
        ("100歳以上", [33]),
        ("年齢不詳", [34]),
    ]

    @classmethod
    def fetch_all(
        cls,
        client: PublicDatasetClient,
        dry_run: bool = False,
    ) -> list[StorePlanningDataSource]:
        data_sources = [
            cls._fetch_estat_population_age_groups(client),
        ]
        if not dry_run:
            for data_source in data_sources:
                StorePlanningDataSourceRepository.save_snapshot(data_source)
        return data_sources

    @classmethod
    def _fetch_estat_population_age_groups(
        cls, client: PublicDatasetClient
    ) -> StorePlanningDataSource:
        csv_text = client.get_text(cls.ESTAT_POPULATION_CSV_URL, encoding="cp932")
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        header = rows[4]
        target_rows = cls._find_target_population_rows(rows)
        total_row = target_rows["総数"]
        age_groups = cls._build_age_group_rows(target_rows)

        return StorePlanningDataSource(
            source_key="estat_population_age_groups_higashi_hokima_2",
            display_name="e-Stat 国勢調査 年齢別人口",
            source_url=cls.ESTAT_POPULATION_SOURCE_URL,
            status="取得済み: Chapter Table 周辺町丁の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=None,
            raw_data={
                "stat_inf_id": cls.ESTAT_POPULATION_STAT_INF_ID,
                "resource_id": cls.ESTAT_POPULATION_RESOURCE_ID,
                "table_name": cls._table_name(header),
                "target_area_name": cls.TARGET_AREA_NAME,
                "city_code": cls.TARGET_CITY_CODE,
                "town_code": cls.TARGET_TOWN_CODE,
                "total_population": cls._to_int(total_row[12]),
                "male_population": cls._to_int(target_rows["男"][12]),
                "female_population": cls._to_int(target_rows["女"][12]),
                "average_age": cls._to_float(
                    cls._value_by_header(header, total_row, "平均年齢")
                ),
                "male_average_age": cls._to_float(
                    cls._value_by_header(header, target_rows["男"], "平均年齢")
                ),
                "female_average_age": cls._to_float(
                    cls._value_by_header(header, target_rows["女"], "平均年齢")
                ),
                "age_groups": age_groups,
            },
        )

    @classmethod
    def _find_target_population_rows(
        cls, rows: list[list[str]]
    ) -> dict[str, list[str]]:
        target_rows = {}
        for row in rows:
            if (
                len(row) > 12
                and row[1] in {"総数", "男", "女"}
                and row[2] == cls.TARGET_CITY_CODE
                and row[3] == cls.TARGET_TOWN_CODE
            ):
                target_rows[row[1]] = row
        if {"総数", "男", "女"}.issubset(target_rows):
            return target_rows
        raise ValueError(
            f"e-Stat CSVに対象地域が見つかりません: {cls.TARGET_AREA_NAME}"
        )

    @classmethod
    def _build_age_group_rows(
        cls, target_rows: dict[str, list[str]]
    ) -> list[dict[str, int | str | None]]:
        age_groups = []
        for label, indexes in cls.AGE_GROUPS:
            total = cls._sum_values(target_rows["総数"], indexes)
            male = cls._sum_values(target_rows["男"], indexes)
            female = cls._sum_values(target_rows["女"], indexes)
            age_groups.append(
                {
                    "label": label,
                    "population": total,
                    "male_population": male,
                    "female_population": female,
                }
            )
        return age_groups

    @classmethod
    def _sum_values(cls, row: list[str], indexes: list[int]) -> int | None:
        values = [cls._to_int(row[index]) for index in indexes]
        if all(value is None for value in values):
            return None
        return sum(value or 0 for value in values)

    @staticmethod
    def _to_int(value: str) -> int | None:
        if value in {"", "X"}:
            return None
        if value == "-":
            return 0
        return int(value.replace(",", ""))

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        if value in {"", None, "X", "-"}:
            return None
        return float(value.replace(",", ""))

    @classmethod
    def _value_by_header(
        cls, header: list[str], row: list[str], column_name: str
    ) -> str | None:
        if column_name not in header:
            return None
        return row[header.index(column_name)]

    @classmethod
    def _table_name(cls, header: list[str]) -> str:
        return cls.ESTAT_POPULATION_TABLE_NAME
