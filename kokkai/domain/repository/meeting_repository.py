from collections.abc import Iterable

from django.db import transaction

from ...models import Meeting, Speech
from ..valueobject.meeting import MeetingIndexRecord, MeetingRecord, SpeechRecord


class MeetingRepository:
    """会議録メタデータと発言の永続化を担当する。"""

    def upsert_indexes(self, records: Iterable[MeetingIndexRecord]) -> list[Meeting]:
        """会議録メタデータを更新し、既存の発言は変更しない。"""
        meetings = []
        for record in records:
            meeting, _ = Meeting.objects.update_or_create(
                min_id=record.issue_id,
                defaults={
                    "meeting_date": record.date_obj,
                    "session_number": record.session,
                    "house": record.name_of_house,
                    "committee": record.name_of_meeting,
                    "meeting_number": record.issue,
                    "url": record.meeting_url,
                    "pdf_url": record.pdf_url or "",
                    "is_current_catalog": True,
                },
            )
            meetings.append(meeting)
        return meetings

    def replace_indexes(self, records: Iterable[MeetingIndexRecord]) -> list[Meeting]:
        """
        Replace the current catalog while preserving saved meeting contents.

        Existing Meeting and Speech rows remain available for later reuse; only
        the flag used by the catalog list is switched.
        """
        with transaction.atomic():
            Meeting.objects.update(is_current_catalog=False)
            return self.upsert_indexes(records)

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
