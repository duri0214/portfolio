import re
import unicodedata

from ..valueobject.meeting import (
    MEETING_METADATA_SPEAKER_NAME,
    MeetingRecord,
    SpeechRecord,
)
from ..valueobject.participant import (
    ParticipantData,
    ParticipantEvidenceData,
    ParticipantExtractionData,
    ParticipantSourceType,
    join_roles,
)


_HONORIFIC_PATTERN = re.compile(r"君(?=$|[\s　、,。])")
_ATTENDANCE_END_MARKERS = ("委員の異動", "本日の会議")
_ATTENDANCE_POSITION_SUFFIXES = ("長", "事", "員", "臣", "官", "人")


def normalize_person_name(value: str | None) -> str:
    """氏名の全角空白と敬称を除去し、突合用の表記へ正規化する。"""

    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = re.sub(r"[（(][^）)]*[）)]", "", normalized)
    normalized = _HONORIFIC_PATTERN.sub("", normalized).strip()
    normalized = re.sub(r"^[○●・]+", "", normalized)
    return re.sub(r"\s+", "", normalized)


def normalize_text(value: str | None) -> str:
    """役職・所属・根拠テキストの空白とUnicode表記を整える。"""

    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip()


class MeetingParticipantExtractor:
    """出席欄で「君」と記載された人物へ発言情報を付加する。"""

    def extract(self, record: MeetingRecord) -> list[ParticipantData]:
        """出席者一覧を正とし、同じ氏名の出席者へ発言情報だけを付加して返す。"""

        builders: dict[str, ParticipantExtractionData] = {}
        for order, entry in enumerate(self._extract_attendance_entries(record)):
            builder = builders.setdefault(
                entry.name,
                ParticipantExtractionData(
                    name=entry.name,
                    attendance_order=order,
                    source_text=entry.source_text,
                    source_speech_id=entry.source_speech_id,
                    source_url=entry.source_url,
                    source_speech_order=entry.source_speech_order,
                ),
            )
            builder.attendance_position = (
                builder.attendance_position or entry.speaker_position
            )
            self._add_evidence(
                builder,
                ParticipantEvidenceData(
                    source_type=ParticipantSourceType.ATTENDANCE,
                    source_meeting_id=record.issue_id,
                    source_speech_id=entry.source_speech_id,
                    source_url=entry.source_url,
                    source_text=entry.source_text,
                    speech_order=entry.source_speech_order,
                    speaker_position=entry.speaker_position,
                    speaker_role="",
                    affiliation="",
                ),
            )

        for speech in sorted(record.speech_records, key=lambda item: item.speech_order):
            if not self._is_speech_record(speech):
                continue
            builder = builders.get(normalize_person_name(speech.speaker))
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

        return [
            ParticipantData(
                name=builder.name,
                name_yomi=builder.name_yomi,
                attendance_position=builder.attendance_position,
                speaker_position=builder.speaker_position
                or builder.attendance_position,
                speaker_role=builder.speaker_role,
                affiliation=builder.affiliation,
                has_spoken=builder.has_spoken,
                speech_count=builder.speech_count,
                source_meeting_id=record.issue_id,
                source_url=record.meeting_url,
                source_text=builder.source_text,
                evidences=tuple(builder.evidences),
            )
            for builder in sorted(
                builders.values(),
                key=lambda builder: (builder.attendance_order, builder.name),
            )
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
    ) -> list[ParticipantExtractionData]:
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

        entries: list[ParticipantExtractionData] = []
        inherited_position = ""
        is_attendance_section = False
        for raw_line in metadata_speech.speech.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(marker in line for marker in _ATTENDANCE_END_MARKERS):
                break
            if not is_attendance_section:
                if "出席" not in line:
                    continue
                is_attendance_section = True
            line_entries = self._parse_attendance_line(
                line, metadata_speech, inherited_position
            )
            entries.extend(line_entries)
            if line_entries:
                continue

            if line.startswith(("（", "(")):
                continue
            position = self._attendance_position(line)
            inherited_position = position if position.endswith("臣") else ""
        return entries

    @staticmethod
    def _parse_attendance_line(
        line: str, metadata_speech: SpeechRecord, inherited_position: str = ""
    ) -> list[ParticipantExtractionData]:
        entries: list[ParticipantExtractionData] = []
        previous_end = 0
        for match in _HONORIFIC_PATTERN.finditer(line):
            token = line[previous_end : match.start()]
            name = MeetingParticipantExtractor._attendance_name(token)
            if name:
                position = MeetingParticipantExtractor._attendance_position(token)
                if inherited_position and token.lstrip().startswith(("（", "(")):
                    position = join_roles(inherited_position, position)
                elif not position:
                    position = inherited_position
                entries.append(
                    ParticipantExtractionData(
                        name=name,
                        attendance_order=len(entries),
                        source_text=line,
                        source_speech_id=metadata_speech.speech_id,
                        source_url=metadata_speech.speech_url,
                        source_speech_order=metadata_speech.speech_order,
                        speaker_position=position,
                    )
                )
            previous_end = match.end()
        return entries

    @staticmethod
    def _attendance_position(value: str) -> str:
        """出席欄で氏名の前に明記された役職を取り出す。"""

        normalized = unicodedata.normalize("NFKC", value).strip()
        annotation = re.match(r"^[（(]([^）)]*)[）)]", normalized)
        if annotation:
            return normalize_text(annotation.group(1))

        parts = re.split(r"[\s　]+", normalized, maxsplit=1)
        if len(parts) == 1 and normalized.endswith(_ATTENDANCE_POSITION_SUFFIXES):
            return normalize_text(normalized)
        if len(parts) < 2 or not parts[0].endswith(_ATTENDANCE_POSITION_SUFFIXES):
            return ""
        return normalize_text(parts[0])

    @staticmethod
    def _attendance_name(value: str) -> str:
        """出席欄の「君」直前の表記から氏名部分を取り出す。"""

        normalized = unicodedata.normalize("NFKC", value)
        annotation = re.match(r"^[\s　]*[（(][^）)]*[）)][\s　]*", normalized)
        if annotation:
            normalized = normalized[annotation.end() :]
        else:
            parts = re.split(r"[\s　]+", normalized.strip(), maxsplit=1)
            if len(parts) > 1 and parts[0].endswith(_ATTENDANCE_POSITION_SUFFIXES):
                normalized = parts[1]
        return normalize_person_name(normalized)

    @staticmethod
    def _add_evidence(
        builder: ParticipantExtractionData, evidence: ParticipantEvidenceData
    ) -> None:
        key = (
            evidence.source_type,
            evidence.source_speech_id or "",
            evidence.source_text,
        )
        if key not in builder.evidence_keys:
            builder.evidence_keys.add(key)
            builder.evidences.append(evidence)


ParticipantExtractor = MeetingParticipantExtractor
