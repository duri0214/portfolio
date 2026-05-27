from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FolderStats:
    """
    フォルダ別統計情報

    Attributes:
        folder: フォルダ名
        device_name: デバイス名 (集計クエリから取得される代表機材名)
        count: データ件数
        min_memory: 最小メモリー番号
        max_memory: 最大メモリー番号
        min_datetime: 最小測定日時
        max_datetime: 最大測定日時
        device_names: 機材名リスト (後続処理で追加される場合がある)
        land_block_names: 圃場ブロック名リスト (後続処理で追加される場合がある)
        land_ledger_info: 帳簿情報リスト (後続処理で追加される場合がある)
    """

    folder: str
    device_name: str
    count: int
    min_memory: int
    max_memory: int
    min_datetime: datetime
    max_datetime: datetime

    # 関連付け情報（LandLedgerRepository等で後付けされる場合がある）
    device_names: list[str] = field(default_factory=list)
    land_block_names: list[str] = field(default_factory=list)
    land_ledger_info: list[dict] = field(default_factory=list)
