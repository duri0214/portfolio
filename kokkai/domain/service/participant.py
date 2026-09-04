import re
import unicodedata
from dataclasses import dataclass, field

from ..valueobject.meeting import (
    MEETING_METADATA_SPEAKER_NAME,
    MeetingRecord,
    SpeechRecord,
)
from ..valueobject.participant import (
    ParticipantAttendanceType,
    ParticipantData,
    ParticipantEvidenceData,
    ParticipantSourceType,
)


_HONORIFIC_PATTERN = re.compile(r"(?:君|氏|さん)(?=$|[\s　、,。])")
_ROLE_RULES = (
    ("委員外の出席者", ParticipantAttendanceType.OTHER, "委員外の出席者"),
    ("出席委員", ParticipantAttendanceType.COMMITTEE_MEMBER, "出席委員"),
    (
        "国家公安委員会委員長",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "国家公安委員会委員長",
    ),
    ("副委員長", ParticipantAttendanceType.CHAIR, "副委員長"),
    ("委員長", ParticipantAttendanceType.CHAIR, "委員長"),
    ("副議長", ParticipantAttendanceType.CHAIR, "副議長"),
    ("議長", ParticipantAttendanceType.CHAIR, "議長"),
    ("副会長", ParticipantAttendanceType.CHAIR, "副会長"),
    ("会長", ParticipantAttendanceType.CHAIR, "会長"),
    (
        "内閣総理大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "内閣総理大臣",
    ),
    ("総務大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "総務大臣"),
    ("外務大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "外務大臣"),
    ("財務大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "財務大臣"),
    (
        "文部科学大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "文部科学大臣",
    ),
    (
        "厚生労働大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "厚生労働大臣",
    ),
    (
        "農林水産大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "農林水産大臣",
    ),
    (
        "経済産業大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "経済産業大臣",
    ),
    (
        "国土交通大臣",
        ParticipantAttendanceType.GOVERNMENT_OFFICIAL,
        "国土交通大臣",
    ),
    ("防衛大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "防衛大臣"),
    ("大臣政務官", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "大臣政務官"),
    ("財務副大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "財務副大臣"),
    ("副大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "副大臣"),
    ("国務大臣", ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "国務大臣"),
    ("予算委員会専門員", ParticipantAttendanceType.STAFF, "専門員"),
    ("政府参考人", ParticipantAttendanceType.GOVERNMENT_REFERENCE, "政府参考人"),
    ("参考人", ParticipantAttendanceType.REFERENCE, "参考人"),
    ("公述人", ParticipantAttendanceType.PUBLIC_WITNESS, "公述人"),
    ("証人", ParticipantAttendanceType.WITNESS, "証人"),
    ("理事", ParticipantAttendanceType.DIRECTOR, "理事"),
    ("専門員", ParticipantAttendanceType.STAFF, "専門員"),
    ("説明員", ParticipantAttendanceType.STAFF, "説明員"),
    ("委員", ParticipantAttendanceType.COMMITTEE_MEMBER, "委員"),
)
_ROLE_LABELS = {rule[2] for rule in _ROLE_RULES}
_ROLE_MARKERS = tuple(sorted((rule[0] for rule in _ROLE_RULES), key=len, reverse=True))


def normalize_person_name(value: str | None) -> str:
    """氏名の全角空白と敬称を除去し、突合用の表記へ正規化する。"""

    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = re.sub(r"[（(][^）)]*[）)]", "", normalized)
    normalized = _HONORIFIC_PATTERN.sub("", normalized).strip()
    normalized = re.sub(r"^[○●・]+", "", normalized)
    while True:
        for marker in _ROLE_MARKERS:
            if normalized.startswith(marker):
                normalized = normalized[len(marker) :].lstrip()
                break
        else:
            break
    return re.sub(r"\s+", "", normalized)


def normalize_text(value: str | None) -> str:
    """役職・所属・根拠テキストの空白とUnicode表記を整える。"""

    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass(frozen=True)
class _AttendanceEntry:
    """
    出席者欄から1人分切り出した内部データ。

    Attributes:
        name: 正規化した氏名。
        attendance_type: 出席区分。
        attendance_role: 出席欄の役職。
        source_text: 氏名を含む元の行。
        source_speech: 出席者欄を保持するメタデータ発言。
    """

    name: str
    attendance_type: str
    attendance_role: str
    source_text: str
    source_speech: SpeechRecord


@dataclass
class _ParticipantBuilder:
    """
    抽出途中の参加者を出席情報と発言情報から集約する内部状態。

    Attributes:
        name: 正規化氏名。
        name_yomi: 氏名のよみ。
        attendance_type: 出席区分。
        attendance_role: 出席時の役職。
        speaker_position: 発言時の肩書き。
        speaker_role: 発言時の役割。
        affiliation: 発言時の所属会派。
        has_spoken: 発言記録があるかどうか。
        speech_count: 発言記録の件数。
        attendance_order: 出席者欄での順番。
        source_text: 代表して表示する元テキスト。
        evidences: 紐づいた根拠一覧。
        evidence_keys: 重複根拠を除くためのキー。
    """

    name: str
    name_yomi: str | None = None
    attendance_type: str = ParticipantAttendanceType.OTHER
    attendance_role: str = ""
    speaker_position: str = ""
    speaker_role: str = ""
    affiliation: str = ""
    has_spoken: bool = False
    speech_count: int = 0
    attendance_order: int | None = None
    source_text: str = ""
    evidences: list[ParticipantEvidenceData] = field(default_factory=list)
    evidence_keys: set[tuple[str, str, str]] = field(default_factory=set)


class MeetingParticipantExtractor:
    """会議録情報の出席者を母集団とし、発言記録を付加して参加者を抽出する。"""

    def extract(self, record: MeetingRecord) -> list[ParticipantData]:
        """出席者一覧を正とし、同じ氏名の出席者へ発言情報だけを付加して返す。"""

        builders: dict[str, _ParticipantBuilder] = {}
        attendance_entries = self._extract_attendance_entries(record)

        for order, entry in enumerate(attendance_entries):
            builder = builders.setdefault(entry.name, _ParticipantBuilder(entry.name))
            if builder.attendance_order is None:
                builder.attendance_order = order
                builder.attendance_type = entry.attendance_type
            if not builder.attendance_role or entry.attendance_role != "出席委員":
                builder.attendance_role = entry.attendance_role
            if not builder.source_text:
                builder.source_text = entry.source_text
            self._add_evidence(
                builder,
                ParticipantEvidenceData(
                    source_type=ParticipantSourceType.ATTENDANCE,
                    source_meeting_id=record.issue_id,
                    source_speech_id=entry.source_speech.speech_id,
                    source_url=entry.source_speech.speech_url,
                    source_text=entry.source_text,
                    speech_order=entry.source_speech.speech_order,
                    speaker_position="",
                    speaker_role="",
                    affiliation="",
                ),
            )

        for speech in sorted(record.speech_records, key=lambda item: item.speech_order):
            if not self._is_speech_record(speech):
                continue

            name = normalize_person_name(speech.speaker)
            if not name:
                continue
            builder = builders.get(name)
            if builder is None:
                continue
            builder.has_spoken = True
            builder.speech_count += 1
            builder.name_yomi = (
                builder.name_yomi or normalize_text(speech.speaker_yomi) or None
            )
            builder.speaker_position = builder.speaker_position or normalize_text(
                speech.speaker_position
            )
            builder.speaker_role = builder.speaker_role or normalize_text(
                speech.speaker_role
            )
            builder.affiliation = builder.affiliation or normalize_text(
                speech.speaker_group
            )
            if not builder.source_text:
                builder.source_text = speech.speech or ""
            self._add_evidence(
                builder,
                ParticipantEvidenceData(
                    source_type=ParticipantSourceType.SPEECH,
                    source_meeting_id=record.issue_id,
                    source_speech_id=speech.speech_id,
                    source_url=speech.speech_url,
                    source_text=speech.speech or "",
                    speech_order=speech.speech_order,
                    speaker_position=normalize_text(speech.speaker_position),
                    speaker_role=normalize_text(speech.speaker_role),
                    affiliation=normalize_text(speech.speaker_group),
                ),
            )

        sorted_builders = sorted(
            builders.values(),
            key=lambda builder: (
                builder.attendance_order,
                builder.name,
            ),
        )
        return [
            ParticipantData(
                name=builder.name,
                name_yomi=builder.name_yomi,
                attendance_type=builder.attendance_type,
                attendance_role=builder.attendance_role,
                speaker_position=builder.speaker_position,
                speaker_role=builder.speaker_role,
                affiliation=builder.affiliation,
                has_spoken=builder.has_spoken,
                speech_count=builder.speech_count,
                source_meeting_id=record.issue_id,
                source_url=record.meeting_url,
                source_text=builder.source_text,
                evidences=tuple(builder.evidences),
            )
            for builder in sorted_builders
        ]

    @staticmethod
    def _is_speech_record(speech: SpeechRecord) -> bool:
        return (
            speech.speaker != MEETING_METADATA_SPEAKER_NAME
            and bool(normalize_text(speech.speech))
            and bool(normalize_person_name(speech.speaker))
        )

    def _extract_attendance_entries(
        self, record: MeetingRecord
    ) -> list[_AttendanceEntry]:
        metadata_speech = next(
            (
                speech
                for speech in record.speech_records
                if speech.speaker == MEETING_METADATA_SPEAKER_NAME
            ),
            None,
        )
        if metadata_speech is None or not metadata_speech.speech:
            return []

        entries: list[_AttendanceEntry] = []
        is_attendance_section = False
        default_type = ParticipantAttendanceType.OTHER
        default_role = ""
        pending_type: str | None = None
        pending_role = ""

        for raw_line in metadata_speech.speech.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "委員の異動" in line or line.startswith("本日の会議"):
                break
            if not is_attendance_section:
                section = self._detect_section(line)
                if section is None:
                    continue
                is_attendance_section = True
                default_type, default_role = section

            section = self._detect_section(line)
            if section is not None:
                default_type, default_role = section

            role_rule = self._detect_role(line)
            line_entries = self._parse_attendance_line(
                line,
                metadata_speech,
                pending_type or default_type,
                pending_role or default_role,
            )
            entries.extend(line_entries)

            if line_entries:
                pending_type = None
                pending_role = ""
            elif role_rule is not None:
                pending_type, pending_role = role_rule
                default_type, default_role = role_rule

        return entries

    @staticmethod
    def _detect_section(line: str) -> tuple[str, str] | None:
        normalized = normalize_text(line)
        if "出席委員" in normalized:
            return ParticipantAttendanceType.COMMITTEE_MEMBER, "出席委員"
        if "出席国務大臣" in normalized:
            return ParticipantAttendanceType.GOVERNMENT_OFFICIAL, "国務大臣"
        if "出席者" in normalized:
            return ParticipantAttendanceType.OTHER, "出席者"
        return None

    @staticmethod
    def _detect_role(value: str) -> tuple[str, str] | None:
        normalized = normalize_text(value)
        matches = [
            (
                normalized.rfind(marker) + len(marker),
                len(marker),
                attendance_type,
                role,
            )
            for marker, attendance_type, role in _ROLE_RULES
            if marker in normalized
        ]
        if not matches:
            return None
        _, _, attendance_type, role = max(matches)
        return attendance_type, role

    @staticmethod
    def _parse_attendance_line(
        line: str,
        metadata_speech: SpeechRecord,
        default_type: str,
        default_role: str,
    ) -> list[_AttendanceEntry]:
        entries: list[_AttendanceEntry] = []
        previous_end = 0
        matches = list(_HONORIFIC_PATTERN.finditer(line))
        for match in matches:
            token = line[previous_end : match.start()]
            role_rule = MeetingParticipantExtractor._detect_role(token)
            attendance_type, attendance_role = role_rule or (
                default_type,
                default_role,
            )
            name = normalize_person_name(token)
            if name and name not in _ROLE_LABELS:
                entries.append(
                    _AttendanceEntry(
                        name=name,
                        attendance_type=attendance_type,
                        attendance_role=attendance_role,
                        source_text=line,
                        source_speech=metadata_speech,
                    )
                )
            previous_end = match.end()
        return entries

    @staticmethod
    def _add_evidence(
        builder: _ParticipantBuilder, evidence: ParticipantEvidenceData
    ) -> None:
        key = (
            evidence.source_type,
            evidence.source_speech_id or "",
            evidence.source_text,
        )
        if key in builder.evidence_keys:
            return
        builder.evidence_keys.add(key)
        builder.evidences.append(evidence)


# 抽出処理の名称を用途に合わせて呼び出せるようにする。
ParticipantExtractor = MeetingParticipantExtractor
