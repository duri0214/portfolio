from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StorePlanningDataSource:
    """
    出店計画画面へ表示する外部データソースの取得結果。

    Attributes:
        source_key: データソースを識別するキー。
        display_name: 画面に表示するデータソース名。
        source_url: 提供元を確認できる公開URL。
        status: 取得・利用状態。
        data_period: 提供元データの対象期間や更新頻度。
        source_updated_at: 提供元が公表している更新日時。
        raw_data: 提供元レスポンスから保存したメタ情報。
    """

    source_key: str
    display_name: str
    source_url: str
    status: str
    data_period: str
    source_updated_at: datetime | None
    raw_data: dict


@dataclass(frozen=True)
class StorePlanningTargetLocation:
    """
    出店計画で人口分析の対象にする店舗候補地。

    Attributes:
        slug: URLパラメータと保存キーに使う識別子。
        name: 画面に表示する店舗名または候補地名。
        address: 店舗候補地の住所。
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
    StorePlanningTargetLocation(
        slug="higashi-hokima-1",
        name="東保木間一丁目 候補地",
        address="東京都足立区東保木間一丁目",
        latitude=35.793608,
        longitude=139.811938,
        city_code="13121",
        town_code="073001",
        population_area="東京都足立区東保木間一丁目",
    ),
]
