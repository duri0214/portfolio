import re
from datetime import datetime

from django.utils import timezone

from shopping.domain.dataprovider.public_dataset import PublicDatasetClient
from shopping.domain.repository.store_planning import StorePlanningDataSourceRepository
from shopping.domain.valueobject.store_planning import StorePlanningDataSource


class StorePlanningDataSourceService:
    """出店計画で使う外部データソースのメタ情報を取得して保存する。"""

    TOKYO_TRAFFIC_DATASET_API_URL = (
        "https://catalog.data.metro.tokyo.lg.jp/api/3/action/package_show"
        "?id=t000022d0000000035"
    )
    NPA_ACCIDENT_OPEN_DATA_URL = (
        "https://www.npa.go.jp/publications/statistics/koutsuu/opendata/"
        "index_opendata.html"
    )
    ESTAT_GIS_URL = "https://www.e-stat.go.jp/gis/gislp/"

    @classmethod
    def fetch_all(
        cls,
        client: PublicDatasetClient,
        dry_run: bool = False,
    ) -> list[StorePlanningDataSource]:
        data_sources = [
            cls._fetch_tokyo_traffic_dataset(client),
            cls._fetch_npa_accident_open_data(client),
            cls._fetch_estat_gis_page(client),
        ]
        if not dry_run:
            for data_source in data_sources:
                StorePlanningDataSourceRepository.save_snapshot(data_source)
        return data_sources

    @classmethod
    def _fetch_tokyo_traffic_dataset(
        cls, client: PublicDatasetClient
    ) -> StorePlanningDataSource:
        response = client.get_json(cls.TOKYO_TRAFFIC_DATASET_API_URL)
        result = response["result"]
        resources = result.get("resources", [])
        resource_names = [resource.get("name", "") for resource in resources]
        source_updated_at = cls._parse_datetime(result.get("metadata_modified"))
        update_frequency = cls._find_extra_value(result, "更新頻度")

        return StorePlanningDataSource(
            source_key="keishicho_traffic_volume",
            display_name=result.get("title", "交通量統計表"),
            source_url=result.get("url") or cls.TOKYO_TRAFFIC_DATASET_API_URL,
            status=f"取得済み: ZIPリソース {len(resources)} 件",
            data_period=update_frequency or "更新頻度未取得",
            source_updated_at=source_updated_at,
            raw_data={
                "package_name": result.get("name"),
                "organization": result.get("organization", {}).get("title"),
                "resource_names": resource_names,
            },
        )

    @classmethod
    def _fetch_npa_accident_open_data(
        cls, client: PublicDatasetClient
    ) -> StorePlanningDataSource:
        html = client.get_text(cls.NPA_ACCIDENT_OPEN_DATA_URL)
        years = sorted(set(re.findall(r"opendata_(20\d{2})\.html", html)))
        latest_year = years[-1] if years else ""
        status = "取得済み"
        if latest_year:
            status = f"取得済み: {latest_year}年までの年度リンク"

        return StorePlanningDataSource(
            source_key="npa_traffic_accident",
            display_name="警察庁 交通事故統計オープンデータ",
            source_url=cls.NPA_ACCIDENT_OPEN_DATA_URL,
            status=status,
            data_period=f"{years[0]}年から{latest_year}年" if years else "年度未取得",
            source_updated_at=None,
            raw_data={"years": years},
        )

    @classmethod
    def _fetch_estat_gis_page(
        cls, client: PublicDatasetClient
    ) -> StorePlanningDataSource:
        html = client.get_text(cls.ESTAT_GIS_URL)
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        page_title = title_match.group(1).strip() if title_match else "jSTAT MAP"

        return StorePlanningDataSource(
            source_key="estat_jstat_map",
            display_name="jSTAT MAP / 国勢調査",
            source_url=cls.ESTAT_GIS_URL,
            status="取得済み: 公式ページ到達確認",
            data_period="統計表ごとの対象期間はAPI取得時に確定",
            source_updated_at=None,
            raw_data={"page_title": page_title},
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    @staticmethod
    def _find_extra_value(result: dict, key: str) -> str:
        for extra in result.get("extras", []):
            if extra.get("key") == key:
                return extra.get("value", "")
        return ""
