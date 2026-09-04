from dataclasses import dataclass
from datetime import date, datetime


MEETING_METADATA_SPEAKER_NAME = "会議録情報"


@dataclass(frozen=True)
class SpeechRecord:
    """
    会議単位出力APIから取得した発言データ。

    Attributes:
        speech_id: 発言ID。
        speaker: 発言者名。
        speaker_yomi: 発言者よみ。
        speaker_group: 発言者所属会派。
        speaker_position: 発言者肩書き。
        speaker_role: 発言者役割。
        speech: 発言本文。
        speech_order: 会議録内の発言順。
        start_page: 掲載開始ページ。
        create_time: レコード登録日時。
        update_time: レコード更新日時。
        speech_url: 発言URL。
    """

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
    """
    会議単位出力APIから取得した、全文を含む会議録データ。

    Attributes:
        issue_id: 会議録ID。
        image_kind: イメージ種別。
        search_object: 検索対象箇所。
        session: 国会回次。
        name_of_house: 院名。
        name_of_meeting: 会議名。
        issue: 号数。
        date: 開催日。
        closing: 閉会中フラグ。
        speech_records: 会議に含まれる発言一覧。
        meeting_url: 会議録URL。
        pdf_url: PDF URL。
    """

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
    def date_obj(self) -> date:
        return datetime.strptime(self.date, "%Y-%m-%d").date()


@dataclass(frozen=True)
class MeetingSearchResult:
    """
    会議単位出力APIの検索結果。

    Attributes:
        number_of_records: 検索結果の総件数。
        number_of_return_records: 今回返却された件数。
        start_record: 取得開始位置。
        next_record_position: 次ページの開始位置。
        meeting_records: 全文を含む会議録一覧。
    """

    number_of_records: int
    number_of_return_records: int
    start_record: int
    next_record_position: int | None
    meeting_records: list[MeetingRecord]


@dataclass(frozen=True)
class MeetingCatalogRecord:
    """
    会議単位簡易出力APIから取得した、本文を含まない会議録メタデータ。

    Attributes:
        issue_id: 会議録ID。
        image_kind: イメージ種別。
        search_object: 検索対象箇所。
        session: 国会回次。
        name_of_house: 院名。
        name_of_meeting: 会議名。
        issue: 号数。
        date: 開催日。
        closing: 閉会中フラグ。
        meeting_url: 会議録URL。
        pdf_url: PDF URL。
    """

    issue_id: str
    image_kind: str
    search_object: int
    session: int
    name_of_house: str
    name_of_meeting: str
    issue: str
    date: str
    closing: str | None
    meeting_url: str
    pdf_url: str | None

    @property
    def date_obj(self) -> date:
        return datetime.strptime(self.date, "%Y-%m-%d").date()


@dataclass(frozen=True)
class MeetingCatalogSearchResult:
    """
    会議単位簡易出力APIの検索結果。

    Attributes:
        number_of_records: 検索結果の総件数。
        number_of_return_records: 今回返却された件数。
        start_record: 取得開始位置。
        next_record_position: 次ページの開始位置。
        meeting_catalog_records: 本文を含まない会議録メタデータ一覧。
    """

    number_of_records: int
    number_of_return_records: int
    start_record: int
    next_record_position: int | None
    meeting_catalog_records: list[MeetingCatalogRecord]
