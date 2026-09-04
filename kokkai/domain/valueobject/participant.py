from dataclasses import dataclass
from enum import StrEnum


class ParticipantAttendanceType(StrEnum):
    """
    会議録の出席者欄から判定する参加区分。

    Attributes:
        CHAIR: 委員長、議長など会議の議事を主宰する参加者。
        DIRECTOR: 理事。
        COMMITTEE_MEMBER: 出席委員。
        GOVERNMENT_OFFICIAL: 国務大臣などの政府側出席者。
        GOVERNMENT_REFERENCE: 政府参考人。
        REFERENCE: 参考人。
        WITNESS: 証人。
        PUBLIC_WITNESS: 公述人。
        STAFF: 専門員、説明員などの事務局側参加者。
        OTHER: 上記に分類できない出席者。
        SPEAKER_ONLY: 出席者欄で確認できず、発言記録だけから抽出した人物。
    """

    CHAIR = "chair"
    DIRECTOR = "director"
    COMMITTEE_MEMBER = "committee_member"
    GOVERNMENT_OFFICIAL = "government_official"
    GOVERNMENT_REFERENCE = "government_reference"
    REFERENCE = "reference"
    WITNESS = "witness"
    PUBLIC_WITNESS = "public_witness"
    STAFF = "staff"
    OTHER = "other"
    SPEAKER_ONLY = "speaker_only"


class ParticipantSourceType(StrEnum):
    """
    参加者の根拠になった会議録内の情報種別。

    Attributes:
        ATTENDANCE: 会議録情報に含まれる出席者一覧。
        SPEECH: 発言単位の発言者情報と本文。
    """

    ATTENDANCE = "attendance"
    SPEECH = "speech"


@dataclass(frozen=True)
class ParticipantEvidenceData:
    """
    参加者を会議録へ追跡するための根拠データ。

    Attributes:
        source_type: 出席者一覧または発言記録の種別。
        source_meeting_id: 公式 API の会議録 ID。
        source_speech_id: 公式 API の発言 ID。出席者一覧ではメタデータ発言 ID。
        source_url: 会議録または発言の公式 URL。
        source_text: 抽出対象になった元テキスト。
        speech_order: 発言記録の発言順。出席者一覧では0番。
        speaker_position: 発言時の肩書き。
        speaker_role: 発言時の役割。
        affiliation: 発言時の所属会派。
    """

    source_type: str
    source_meeting_id: str
    source_speech_id: str | None
    source_url: str
    source_text: str
    speech_order: int | None
    speaker_position: str
    speaker_role: str
    affiliation: str


@dataclass(frozen=True)
class ParticipantData:
    """
    会議録から抽出・正規化した会議参加者。

    Attributes:
        name: 敬称と空白を除去した正規化氏名。
        name_yomi: 公式 API が返す氏名のよみ。
        attendance_type: 出席者欄から判定した参加区分。
        attendance_role: 出席者欄に記載された役職。
        speaker_position: 発言時の肩書き。
        speaker_role: 発言時の役割。
        affiliation: 発言時の所属会派。
        has_spoken: 発言記録が1件以上あるかどうか。
        speech_count: 発言記録の件数。
        source_meeting_id: 抽出元の会議録 ID。
        source_url: 抽出元の会議録 URL。
        source_text: 参加者に最初に紐づいた抽出元テキスト。
        evidences: 参加者を一次ソースへ戻るための根拠一覧。
    """

    name: str
    name_yomi: str | None
    attendance_type: str
    attendance_role: str
    speaker_position: str
    speaker_role: str
    affiliation: str
    has_spoken: bool
    speech_count: int
    source_meeting_id: str
    source_url: str
    source_text: str
    evidences: tuple[ParticipantEvidenceData, ...]

    @property
    def role(self) -> str:
        """表示用に、発言時の役職を優先して返す。"""

        return self.speaker_position or self.speaker_role or self.attendance_role


@dataclass(frozen=True)
class ParticipantActorData:
    """
    シナリオのアクター候補として利用する参加者の読み取り値。

    Attributes:
        participant_id: 永続化された会議参加者の ID。
        name: 正規化氏名。
        name_yomi: 氏名のよみ。
        attendance_type: 出席区分。
        attendance_role: 出席時の役職。
        speaker_position: 発言時の肩書き。
        speaker_role: 発言時の役割。
        affiliation: 発言時の所属会派。
        has_spoken: 発言記録があるかどうか。
        speech_count: 発言記録の件数。
    """

    participant_id: int
    name: str
    name_yomi: str | None
    attendance_type: str
    attendance_role: str
    speaker_position: str
    speaker_role: str
    affiliation: str
    has_spoken: bool
    speech_count: int

    @property
    def role(self) -> str:
        """表示用に、発言時の役職を優先して返す。"""

        return self.speaker_position or self.speaker_role or self.attendance_role
