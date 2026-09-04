from collections.abc import Iterable

from django.db import transaction

from ...models import Meeting, Speech
from ..valueobject.meeting import MeetingCatalogRecord, MeetingRecord, SpeechRecord


class MeetingRepository:
    """会議録メタデータと発言の永続化を担当する。"""

    def rebuild_meetings(self, records: Iterable[MeetingCatalogRecord]) -> int:
        """
        検索結果から会議録カタログを再構築する。

        既存の会議録を削除すると、紐づく本文・シナリオもカスケード削除される。
        その後、検索結果だけを保存する。
        """
        with transaction.atomic():
            Meeting.objects.all().delete()
            Meeting.objects.bulk_create(
                [
                    Meeting(
                        meeting_date=record.date_obj,
                        session_number=record.session,
                        house=record.name_of_house,
                        committee=record.name_of_meeting,
                        meeting_number=record.issue,
                        min_id=record.issue_id,
                        url=record.meeting_url,
                        pdf_url=record.pdf_url or "",
                    )
                    for record in records
                ]
            )
            return Meeting.objects.count()

    def replace_meeting_contents(
        self,
        record: MeetingRecord,
        speeches: Iterable[tuple[SpeechRecord, int]],
    ) -> Meeting:
        """選択された会議録だけの本文と発言を更新する。"""
        with transaction.atomic():
            meeting, created = Meeting.objects.update_or_create(
                min_id=record.issue_id,
                defaults={
                    "meeting_date": record.date_obj,
                    "session_number": record.session,
                    "house": record.name_of_house,
                    "committee": record.name_of_meeting,
                    "meeting_number": record.issue,
                    "url": record.meeting_url,
                    "pdf_url": record.pdf_url or "",
                },
            )
            if not created:
                meeting.speeches.all().delete()
            Speech.objects.bulk_create(
                [
                    Speech(
                        meeting=meeting,
                        speaker_name=speech.speaker,
                        speaker_role=speech.speaker_role,
                        speaker_affiliation=speech.speaker_group,
                        speech_text=speech.speech or "",
                        speech_order=speech_order,
                        source_url=speech.speech_url,
                    )
                    for speech, speech_order in speeches
                ]
            )
        return meeting
