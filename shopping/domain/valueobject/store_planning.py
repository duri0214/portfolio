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
