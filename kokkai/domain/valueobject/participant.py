from dataclasses import dataclass, field
from enum import StrEnum


class ParticipantSourceType(StrEnum):
    """参加者の根拠になった会議録内の情報種別。"""

    ATTENDANCE = "attendance"
    SPEECH = "speech"


def join_roles(*roles: str | None) -> str:
    """重複を除いた役職を表示用の文字列へまとめる。"""

    unique_roles: list[str] = []
    for role in roles:
        normalized = (role or "").strip()
        if normalized and normalized not in unique_roles:
            unique_roles.append(normalized)
    return " / ".join(unique_roles)


@dataclass(frozen=True)
class ParticipantEvidenceData:
    """参加者を会議録へ追跡するための根拠データ。"""

    source_type: str
    source_meeting_id: str
    source_speech_id: str | None
    source_url: str
    source_text: str
    speech_order: int | None
    speaker_position: str
    speaker_role: str
    affiliation: str


@dataclass
class ParticipantExtractionData:
    """会議録から抽出中の参加者と根拠を保持する値。"""

    name: str
    attendance_order: int
    source_text: str
    source_speech_id: str
    source_url: str
    source_speech_order: int
    name_yomi: str | None = None
    attendance_position: str = ""
    speaker_position: str = ""
    speaker_role: str = ""
    affiliation: str = ""
    has_spoken: bool = False
    speech_count: int = 0
    evidences: list[ParticipantEvidenceData] = field(default_factory=list)
    evidence_keys: set[tuple[str, str, str]] = field(default_factory=set)


@dataclass(frozen=True)
class ParticipantData:
    """会議録から抽出・正規化した会議参加者。"""

    name: str
    name_yomi: str | None
    attendance_position: str
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
        """表示用に、出席時と発言時の役職を重複なく併記する。"""

        return join_roles(
            self.attendance_position,
            self.speaker_position,
            self.speaker_role,
        )


@dataclass(frozen=True)
class ParticipantSummaryData:
    """会議録情報の出席者を母集団として集計した参加者数。"""

    attendance_count: int
    speaker_count: int


@dataclass(frozen=True)
class ParticipantActorData:
    """シナリオのアクター候補として利用する参加者の読み取り値。"""

    participant_id: int
    name: str
    name_yomi: str | None
    speaker_position: str
    speaker_role: str
    affiliation: str
    has_spoken: bool
    speech_count: int

    @property
    def role(self) -> str:
        """表示用に、発言時の役職を重複なく併記する。"""

        return join_roles(self.speaker_position, self.speaker_role)
