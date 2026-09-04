from datetime import date
from time import sleep

from ..repository.meeting_repository import MeetingRepository
from .kokkai_api import KokkaiAPIClient


class MeetingIndexService:
    """会議本文を取得せず、指定期間の会議録メタデータだけを索引化する。"""

    REQUEST_INTERVAL_SECONDS = 2

    def __init__(
        self,
        client: KokkaiAPIClient | None = None,
        repository: MeetingRepository | None = None,
    ) -> None:
        self.client = client or KokkaiAPIClient()
        self.repository = repository or MeetingRepository()

    def create_index(self, start_date: date, end_date: date) -> int:
        """指定期間の全ページを取得し、保存した会議録メタデータ件数を返す。"""
        start_record: int | None = 1
        records = []

        while start_record is not None:
            result = self.client.search_meeting_indexes(
                start_date, end_date, start_record
            )
            records.extend(result.meeting_index_records)

            next_record_position = result.next_record_position
            if next_record_position and next_record_position > start_record:
                sleep(self.REQUEST_INTERVAL_SECONDS)
                start_record = next_record_position
            else:
                start_record = None

        return self.repository.rebuild_meetings(records)
