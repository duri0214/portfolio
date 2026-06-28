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
        data_sources = cls._fetch_estat_population_age_groups(client)
        if not dry_run:
            for data_source in data_sources:
                StorePlanningDataSourceRepository.save_snapshot(data_source)
        return data_sources

    @classmethod
    def _fetch_estat_population_age_groups(
        cls, client: PublicDatasetClient
    ) -> list[StorePlanningDataSource]:
        csv_text = client.get_text(cls.ESTAT_POPULATION_CSV_URL, encoding="cp932")
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        header = rows[4]
        grouped_rows = cls._group_population_rows(rows)
        return [
            cls._build_population_data_source(header, target_rows)
            for target_rows in grouped_rows.values()
        ]

    @classmethod
    def _build_population_data_source(
        cls,
        header: list[str],
        target_rows: dict[str, list[str]],
    ) -> StorePlanningDataSource:
        total_row = target_rows["総数"]
        age_groups = cls._build_age_group_rows(target_rows)
        area_name = cls._area_name(total_row)
        city_code = total_row[2]
        town_code = total_row[3]

        return StorePlanningDataSource(
            source_key=cls._source_key(city_code, town_code),
            display_name=f"e-Stat 国勢調査 年齢別人口: {area_name}",
            source_url=cls.ESTAT_POPULATION_SOURCE_URL,
            status=f"取得済み: {area_name} の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=None,
            raw_data={
                **cls._base_raw_data(header, total_row),
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
    def _base_raw_data(cls, header: list[str], total_row: list[str]) -> dict:
        return {
            "stat_inf_id": cls.ESTAT_POPULATION_STAT_INF_ID,
            "resource_id": cls.ESTAT_POPULATION_RESOURCE_ID,
            "table_name": cls._table_name(header),
            "target_area_name": cls._area_name(total_row),
            "prefecture_name": total_row[8],
            "city_name": total_row[9],
            "large_area_name": total_row[10],
            "small_area_name": total_row[11],
            "city_code": total_row[2],
            "town_code": total_row[3],
            "age_groups": [],
        }

    @classmethod
    def _group_population_rows(
        cls, rows: list[list[str]]
    ) -> dict[tuple[str, str], dict[str, list[str]]]:
        grouped_rows = {}
        for row in rows:
            if len(row) <= 12 or row[1] not in {"総数", "男", "女"}:
                continue
            key = (row[2], row[3])
            grouped_rows.setdefault(key, {})[row[1]] = row
        return {
            key: target_rows
            for key, target_rows in grouped_rows.items()
            if {"総数", "男", "女"}.issubset(target_rows)
        }

    @staticmethod
    def _source_key(city_code: str, town_code: str) -> str:
        return f"estat_population_age_groups_{city_code}_{town_code}"

    @staticmethod
    def _area_name(row: list[str]) -> str:
        return "".join(row[index] for index in range(8, 12) if row[index])

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
