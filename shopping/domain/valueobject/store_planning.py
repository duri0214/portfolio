from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from urllib.parse import quote


@dataclass(frozen=True)
class StorePlanningDataSource:
    """
    出店計画画面へ表示する e-Stat 人口CSVの取得・集計結果。

    Attributes:
        source_key: データソースを識別するキー。
        display_name: 画面に表示するデータソース名。
        source_url: e-Statの統計表を確認できる公開URL。
        status: 取得・利用状態。
        data_period: e-Statデータの対象期間。
        source_updated_at: e-Statが公表している更新日時。
        raw_data: e-Stat CSVから保存した集計値とメタ情報。
    """

    source_key: str
    display_name: str
    source_url: str
    status: str
    data_period: str
    source_updated_at: datetime | None
    raw_data: dict


@dataclass(frozen=True)
class StorePlanningArea:
    """
    出店計画で人口分析や地域比較に使う町丁・地域。

    Attributes:
        slug: URLパラメータと保存キーに使う識別子。
        name: 画面に表示する地域名または候補地名。
        address: 地域または候補地の住所。
        latitude: Google Mapsリンクに使う緯度。
        longitude: Google Mapsリンクに使う経度。
        city_code: e-Stat CSVの市区町村コード。
        town_code: e-Stat CSVの町丁字コード。
        population_area: 人口集計に使う町丁字名。
    """

    slug: str
    name: str
    address: str
    latitude: float
    longitude: float
    city_code: str
    town_code: str
    population_area: str

    @property
    def source_key(self) -> str:
        return f"estat_population_age_groups_{self.city_code}_{self.town_code}"

    @property
    def google_maps_url(self) -> str:
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"

    @property
    def area_google_maps_url(self) -> str:
        return f"https://www.google.com/maps/search/?api=1&query={quote(self.population_area)}"

    @property
    def area_google_maps_embed_url(self) -> str:
        return (
            f"https://www.google.com/maps?q={quote(self.population_area)}&output=embed"
        )


@dataclass(frozen=True)
class StorePlanningTargetLocation(StorePlanningArea):
    """出店計画で選択対象にする店舗候補地。"""


STORE_PLANNING_TARGET_LOCATIONS = [
    StorePlanningTargetLocation(
        slug="chapter-table",
        name="Chapter Table",
        address="東京都足立区東保木間二丁目",
        latitude=35.79285640333462,
        longitude=139.81430669359216,
        city_code="13121",
        town_code="073002",
        population_area="東京都足立区東保木間二丁目",
    ),
]

STORE_PLANNING_COMPARISON_AREAS = [
    StorePlanningArea(
        slug="area-higashi-hokima-1",
        name="比較対象地域（東保木間一丁目）",
        address="東京都足立区東保木間一丁目",
        latitude=35.793608,
        longitude=139.811938,
        city_code="13121",
        town_code="073001",
        population_area="東京都足立区東保木間一丁目",
    ),
]
