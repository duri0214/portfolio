from dataclasses import dataclass
import datetime


@dataclass(frozen=True)
class SpeechRecord:
    speech_id: str
    speaker: str
    speaker_yomi: str | None
    speaker_group: str | None
    speaker_position: str | None
    speaker_role: str | None
    speech: str | None
    speech_order: int
    start_page: int | None
    create_time: str
    update_time: str
    speech_url: str


@dataclass(frozen=True)
class MeetingRecord:
    issue_id: str
    image_kind: str
    search_object: int
    session: int
    name_of_house: str
    name_of_meeting: str
    issue: str
    date: str
    closing: str | None
    speech_records: list[SpeechRecord]
    meeting_url: str
    pdf_url: str | None

    @property
    def date_obj(self) -> datetime.date:
        from datetime import datetime

        return datetime.strptime(self.date, "%Y-%m-%d").date()


@dataclass(frozen=True)
class MeetingSearchResult:
    number_of_records: int
    number_of_return_records: int
    start_record: int
    next_record_position: int | None
    meeting_records: list[MeetingRecord]
