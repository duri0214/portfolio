from dataclasses import dataclass
from datetime import date, timedelta

from ..repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from .kokkai_api import KokkaiAPIClient


@dataclass(frozen=True)
class AffiliationImportPage:
    """
    会派観測の一回分の会議録取り込み結果。

    Attributes:
        meeting_count: 今回のAPIページから観測へ反映した会議録数。
        total_meeting_count: 現在の月次期間に含まれる会議録の総数。
        next_record_position: 同じ月次期間で次に取得するAPIレコード位置。
    """

    meeting_count: int
    total_meeting_count: int
    next_record_position: int | None


class AffiliationImportService:
    """ロープレ用データを使わず、公式APIから会派観測を月次で取得する。"""

    def __init__(
        self,
        client: KokkaiAPIClient | None = None,
        repository: AffiliationObservationRepository | None = None,
    ) -> None:
        self.client = client or KokkaiAPIClient()
        self.repository = repository or AffiliationObservationRepository()

    def import_page(
        self, start_date: date, end_date: date, start_record: int
    ) -> AffiliationImportPage:
        """指定月次期間のAPI一ページを取得して会派観測を更新する。"""

        result = self.client.search_meetings(
            start_date,
            end_date,
            start_record=start_record,
        )
        meeting_count = 0
        for record in result.meeting_records:
            self.repository.refresh_for_record(record)
            meeting_count += 1

        return AffiliationImportPage(
            meeting_count=meeting_count,
            total_meeting_count=result.number_of_records,
            next_record_position=result.next_record_position,
        )

    @staticmethod
    def first_chunk_end(start_date: date, end_date: date) -> date:
        """開始日を含む暦月の末日と指定終了日のうち早い日を返す。"""

        next_month_start = (start_date.replace(day=28) + timedelta(days=4)).replace(
            day=1
        )
        return min(next_month_start - timedelta(days=1), end_date)
