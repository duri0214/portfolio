from dataclasses import dataclass
from datetime import date
from time import sleep

from ..repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from .kokkai_api import KokkaiAPIClient


@dataclass(frozen=True)
class AffiliationImportResult:
    """
    指定期間の会派観測取り込み結果。

    Attributes:
        meeting_count: 公式APIから取得して観測へ変換した会議録件数。
        start_date: 取得対象の開始日。
        end_date: 取得対象の終了日。
    """

    meeting_count: int
    start_date: date
    end_date: date


class AffiliationImportService:
    """ロープレ用データを使わず、公式APIから会派観測だけを期間取得する。"""

    REQUEST_INTERVAL_SECONDS = 2

    def __init__(
        self,
        client: KokkaiAPIClient | None = None,
        repository: AffiliationObservationRepository | None = None,
    ) -> None:
        self.client = client or KokkaiAPIClient()
        self.repository = repository or AffiliationObservationRepository()

    def import_period(
        self, start_date: date, end_date: date
    ) -> AffiliationImportResult:
        """指定期間の会議録を全ページ取得し、会派観測を更新して件数を返す。"""

        start_record: int | None = 1
        meeting_count = 0
        while start_record is not None:
            result = self.client.search_meetings(
                start_date,
                end_date,
                start_record=start_record,
            )
            for record in result.meeting_records:
                self.repository.refresh_for_record(record)
                meeting_count += 1

            next_record_position = result.next_record_position
            if next_record_position and next_record_position > start_record:
                sleep(self.REQUEST_INTERVAL_SECONDS)
                start_record = next_record_position
            else:
                start_record = None

        return AffiliationImportResult(meeting_count, start_date, end_date)
