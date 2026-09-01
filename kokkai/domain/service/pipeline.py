from datetime import date

from ..repository.meeting_repository import MeetingRepository
from ..valueobject.meeting import (
    MEETING_METADATA_SPEAKER_NAME,
    MeetingRecord,
)
from .kokkai_api import KokkaiAPIClient


class KokkaiPipeline:
    """
    選択された会議録の全文を発言単位で保存する。

    会議録メタデータの索引化は MeetingIndexService が担当する。
    Embedding登録はシナリオ作成の主経路ではないため、この取り込みでは行わない。
    """

    def __init__(
        self,
        client: KokkaiAPIClient | None = None,
        repository: MeetingRepository | None = None,
    ) -> None:
        self.client = client or KokkaiAPIClient()
        self.repository = repository or MeetingRepository()

    def process_and_save_meetings(self, start_date: date, end_date: date):
        """互換性のため、指定期間の会議録本文をすべて取得・保存する。"""
        print(f"Starting pipeline for period: {start_date} to {end_date}")
        current_start = 1
        while True:
            result = self.client.search_meetings(
                start_date, end_date, start_record=current_start
            )
            if not result.meeting_records:
                print("No more meeting records found.")
                break

            total = result.number_of_records
            print(f"Processing batch starting at {current_start} / {total}")

            for a_meeting in result.meeting_records:
                print(
                    f"  Processing: {a_meeting.date} {a_meeting.name_of_meeting} {a_meeting.issue}"
                )
                try:
                    self._process_meeting_record(a_meeting)
                except Exception as e:
                    print(f"    Error processing a_meeting {a_meeting.issue_id}: {e}")
                    # 1つの会議の失敗が、期間全体のバッチ処理を止めないように制御する。
                    # エラーが発生した会議のDB変更は _process_meeting_record 内でロールバックされるが、
                    # それ以前に完了した会議のデータは保持される。
                    continue

            if (
                not result.next_record_position
                or result.next_record_position > result.number_of_records
            ):
                break
            current_start = result.next_record_position
        print("Pipeline execution completed.")

    def import_selected_meetings(self, meeting_ids: list[str]) -> int:
        """指定された会議録IDだけを全文取得し、保存した件数を返す。"""
        imported_count = 0
        for meeting_id in dict.fromkeys(meeting_ids):
            result = self.client.fetch_meeting(meeting_id)
            for meeting_record in result.meeting_records:
                self._process_meeting_record(meeting_record)
                imported_count += 1
        return imported_count

    def _process_meeting_record(self, a_meeting: MeetingRecord):
        """
        会議録1件の発言をDBへ保存する。

        索引更新ではこのメソッドを呼ばないため、発言の置き換えは発生しない。
        """
        speeches = []
        for speech in a_meeting.speech_records:
            if not speech.speech or speech.speaker == MEETING_METADATA_SPEAKER_NAME:
                continue
            speeches.append((speech, speech.speech_order))
        self.repository.replace_meeting_contents(a_meeting, speeches)
