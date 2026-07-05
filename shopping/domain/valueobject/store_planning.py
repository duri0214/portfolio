from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote


AREA_HIERARCHY_LEVEL_CITY = "1"
AREA_HIERARCHY_LEVEL_TOWN = "2"
AREA_HIERARCHY_LEVEL_PARENT_TOWN = "3"
AREA_HIERARCHY_LEVEL_BLOCK = "4"
AREA_HIERARCHY_LEVEL_LABELS = {
    AREA_HIERARCHY_LEVEL_CITY: "市区町村単位",
    AREA_HIERARCHY_LEVEL_TOWN: "字・町名（異なる字・丁目の地域を含まないもの）",
    AREA_HIERARCHY_LEVEL_PARENT_TOWN: "大字・町名が同じ字・丁目の合計",
    AREA_HIERARCHY_LEVEL_BLOCK: "字・丁目単位",
}


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
        raw_data: e-Stat CSVから保存した集計値とメタ情報。市区町村コード、
            町丁字コード、地域階層レベルは、総務省統計局「令和2年国勢調査
            調査結果の利用案内」のCSV列値をそのまま保持する。
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
        latitude: Google Mapsリンクに使う緯度。未取得の場合は地域名検索を使う。
        longitude: Google Mapsリンクに使う経度。未取得の場合は地域名検索を使う。
        city_code: e-Stat CSVの市区町村コード。
        town_code: e-Stat CSVの町丁字コード。
        population_area: 人口集計に使う町丁字名。
        business_type_label: 画面表示と周辺同業店舗検索に使う業態名。
        business_search_query: 周辺同業店舗を検索するためのGoogle Maps検索語。
            店舗登録フォームでは業態名と同じ値を保存する。
        large_area_name: e-Stat CSVの大字・町名。
        small_area_name: e-Stat CSVの字・丁目名。
        area_hierarchy_level: e-Stat CSVの地域階層レベル。総務省統計局
            「令和2年国勢調査 調査結果の利用案内」に従い、1=市区町村単位、
            2=字・町名（異なる字・丁目の地域を含まないもの）、
            3=大字・町名が同じ字・丁目の合計、4=字・丁目単位を表す。
        comparison_note: 比較対象に選ばれた根拠や注意書き。
    """

    slug: str
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    city_code: str
    town_code: str
    population_area: str
    business_type_label: str = "飲食店"
    business_search_query: str = "レストラン"
    large_area_name: str = ""
    small_area_name: str = ""
    area_hierarchy_level: str = AREA_HIERARCHY_LEVEL_BLOCK
    comparison_note: str = ""

    @property
    def source_key(self) -> str:
        return f"estat_population_age_groups_{self.city_code}_{self.town_code}"

    @property
    def google_maps_url(self) -> str:
        if self.latitude is None or self.longitude is None:
            return self.area_google_maps_url
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"

    @property
    def place_google_maps_embed_url(self) -> str:
        if self.latitude is None or self.longitude is None:
            return self.area_google_maps_embed_url
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}&output=embed"

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
