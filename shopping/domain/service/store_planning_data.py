import csv
import re
from datetime import datetime
from io import StringIO

from django.utils import timezone

from shopping.domain.dataprovider.public_dataset import PublicDatasetClient
from shopping.domain.repository.store_planning import StorePlanningDataSourceRepository
from shopping.domain.valueobject.store_planning import StorePlanningDataSource


class StorePlanningDataSourceService:
    """出店計画で使う外部データソースのメタ情報を取得して保存する。"""

    ESTAT_DATA_CATALOG_API_URL = (
        "https://api.e-stat.go.jp/rest/3.0/app/json/getDataCatalog"
    )
    ESTAT_POPULATION_SOURCE_URL = (
        "https://www.e-stat.go.jp/stat-search/files"
        "?cycle=0&cycle_facet=tclass1%3Acycle&layout=datalist&page=1"
        "&tclass1=000001136472&tclass2=000001159886&tclass3val=0"
        "&toukei=00200521&tstat=000001136464"
    )
    ESTAT_POPULATION_STAT_INF_ID = "000032163275"
    ESTAT_TOKYO_CATALOG_START_POSITION = 13
    TARGET_CITY_CODE = "13121"
    TARGET_TOWN_CODE = "073002"
    TARGET_AREA_NAME = "東京都足立区東保木間二丁目"

    @classmethod
    def fetch_all(
        cls,
        client: PublicDatasetClient,
        estat_app_id: str,
        dry_run: bool = False,
    ) -> list[StorePlanningDataSource]:
        data_sources = [
            cls._fetch_estat_population_age_groups(client, estat_app_id),
        ]
        if not dry_run:
            for data_source in data_sources:
                StorePlanningDataSourceRepository.save_snapshot(data_source)
        return data_sources

    @classmethod
    def _fetch_estat_population_age_groups(
        cls, client: PublicDatasetClient, estat_app_id: str
    ) -> StorePlanningDataSource:
        resource = cls._fetch_population_csv_resource(client, estat_app_id)
        csv_url = resource["URL"]
        csv_text = client.get_text(csv_url, encoding="cp932")
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        header = rows[4]
        target_row = cls._find_target_population_row(rows)
        age_groups = cls._build_age_group_rows(header, target_row)

        return StorePlanningDataSource(
            source_key="estat_population_age_groups_higashi_hokima_2",
            display_name="e-Stat 国勢調査 年齢別人口",
            source_url=cls.ESTAT_POPULATION_SOURCE_URL,
            status="取得済み: Chapter Table 周辺町丁の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=cls._parse_estat_date(resource.get("LAST_MODIFIED_DATE")),
            raw_data={
                "stat_inf_id": cls._extract_stat_inf_id(csv_url),
                "resource_id": resource.get("@id"),
                "table_name": resource.get("TITLE", {}).get("TABLE_NAME"),
                "release_date": resource.get("RELEASE_DATE"),
                "last_modified_date": resource.get("LAST_MODIFIED_DATE"),
                "target_area_name": cls.TARGET_AREA_NAME,
                "city_code": cls.TARGET_CITY_CODE,
                "town_code": cls.TARGET_TOWN_CODE,
                "total_population": cls._to_int(target_row[12]),
                "age_groups": age_groups,
            },
        )

    @classmethod
    def _fetch_population_csv_resource(
        cls, client: PublicDatasetClient, estat_app_id: str
    ) -> dict:
        catalog = client.get_json(
            cls.ESTAT_DATA_CATALOG_API_URL,
            params={
                "appId": estat_app_id,
                "lang": "J",
                "statsCode": "00200521",
                "surveyYears": "2020",
                "dataType": "CSV",
                "limit": 1,
                "startPosition": cls.ESTAT_TOKYO_CATALOG_START_POSITION,
            },
        )
        resources = (
            catalog.get("GET_DATA_CATALOG", {})
            .get("DATA_CATALOG_LIST_INF", {})
            .get("DATA_CATALOG_INF", {})
            .get("RESOURCES", {})
            .get("RESOURCE", [])
        )
        for resource in resources:
            title = resource.get("TITLE", {})
            if str(title.get("TABLE_NO")) == "3":
                return resource
        raise ValueError(
            "e-Statデータカタログに東京都の年齢別人口CSVが見つかりません。"
        )

    @classmethod
    def _find_target_population_row(cls, rows: list[list[str]]) -> list[str]:
        for row in rows:
            if (
                len(row) > 12
                and row[1] == "総数"
                and row[2] == cls.TARGET_CITY_CODE
                and row[3] == cls.TARGET_TOWN_CODE
            ):
                return row
        raise ValueError(
            f"e-Stat CSVに対象地域が見つかりません: {cls.TARGET_AREA_NAME}"
        )

    @classmethod
    def _build_age_group_rows(
        cls, header: list[str], target_row: list[str]
    ) -> list[dict[str, int | str | None]]:
        age_groups = []
        for index in range(13, 34):
            age_groups.append(
                {
                    "label": header[index],
                    "population": cls._to_int(target_row[index]),
                }
            )
        return age_groups

    @staticmethod
    def _to_int(value: str) -> int | None:
        if value in {"", "X"}:
            return None
        if value == "-":
            return 0
        return int(value.replace(",", ""))

    @staticmethod
    def _extract_stat_inf_id(url: str) -> str:
        match = re.search(r"statInfId=([0-9]+)", url)
        return match.group(1) if match else ""

    @staticmethod
    def _parse_estat_date(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed
