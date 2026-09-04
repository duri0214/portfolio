from collections.abc import Iterable

from django.db import transaction

from ...models import Meeting, MeetingParticipant, MeetingParticipantEvidence
from ..valueobject.participant import (
    ParticipantActorData,
    ParticipantData,
    ParticipantSummaryData,
)


class MeetingParticipantRepository:
    """会議参加者と、参加者から公式会議録へ戻る根拠を永続化する。"""

    def replace_for_meeting(
        self, meeting: Meeting, participants: Iterable[ParticipantData]
    ) -> list[MeetingParticipant]:
        """会議単位で参加者と根拠を洗い替え、保存済み参加者を返す。"""

        participant_data = list(participants)
        with transaction.atomic():
            MeetingParticipant.objects.filter(meeting=meeting).delete()
            MeetingParticipant.objects.bulk_create(
                [
                    MeetingParticipant(
                        meeting=meeting,
                        display_order=display_order,
                        name=participant.name,
                        name_yomi=participant.name_yomi or "",
                        attendance_type=participant.attendance_type,
                        attendance_role=participant.attendance_role,
                        speaker_position=participant.speaker_position,
                        speaker_role=participant.speaker_role,
                        affiliation=participant.affiliation,
                        has_spoken=participant.has_spoken,
                        speech_count=participant.speech_count,
                        source_meeting_id=participant.source_meeting_id,
                        source_url=participant.source_url,
                        source_text=participant.source_text,
                    )
                    for display_order, participant in enumerate(participant_data, 1)
                ]
            )
            saved_participants = MeetingParticipant.objects.filter(
                meeting=meeting,
                name__in=[participant.name for participant in participant_data],
            )
            participant_models_by_name = {
                participant.name: participant for participant in saved_participants
            }
            participant_models = [
                participant_models_by_name[participant.name]
                for participant in participant_data
            ]

            evidence_models = []
            for participant_model, participant in zip(
                participant_models, participant_data, strict=True
            ):
                evidence_models.extend(
                    MeetingParticipantEvidence(
                        participant=participant_model,
                        source_type=evidence.source_type,
                        source_meeting_id=evidence.source_meeting_id,
                        source_speech_id=evidence.source_speech_id or "",
                        source_url=evidence.source_url,
                        source_text=evidence.source_text,
                        speech_order=evidence.speech_order,
                        speaker_position=evidence.speaker_position,
                        speaker_role=evidence.speaker_role,
                        affiliation=evidence.affiliation,
                    )
                    for evidence in participant.evidences
                )
            MeetingParticipantEvidence.objects.bulk_create(evidence_models)
        return participant_models

    def list_for_meeting(self, meeting: Meeting):
        """会議の表示順で、根拠を先読みした参加者一覧を返す。"""

        return (
            MeetingParticipant.objects.filter(meeting=meeting)
            .prefetch_related("evidences")
            .order_by("-has_spoken", "-speech_count", "display_order", "pk")
        )

    def get_summary_for_meeting(self, meeting: Meeting) -> ParticipantSummaryData:
        """出席欄と発言記録を別々に数えた会議参加者の集計を返す。"""

        participants = MeetingParticipant.objects.filter(meeting=meeting)
        attendance_participants = participants.filter(
            evidences__source_type=MeetingParticipantEvidence.SourceType.ATTENDANCE
        ).distinct()
        committee_member_count = attendance_participants.filter(
            attendance_type__in=(
                MeetingParticipant.AttendanceType.CHAIR,
                MeetingParticipant.AttendanceType.DIRECTOR,
                MeetingParticipant.AttendanceType.COMMITTEE_MEMBER,
            )
        ).count()
        attendance_count = attendance_participants.count()
        return ParticipantSummaryData(
            attendance_count=attendance_count,
            committee_member_count=committee_member_count,
            non_committee_attendance_count=attendance_count - committee_member_count,
            speaker_count=attendance_participants.filter(has_spoken=True).count(),
        )

    def get_actor_candidates(self, meeting: Meeting) -> list[ParticipantActorData]:
        """発言者を優先した、シナリオ用アクター候補を返す。"""

        participants = MeetingParticipant.objects.filter(meeting=meeting).order_by(
            "-has_spoken", "-speech_count", "display_order", "pk"
        )
        return [
            ParticipantActorData(
                participant_id=participant.pk,
                name=participant.name,
                name_yomi=participant.name_yomi or None,
                attendance_type=participant.attendance_type,
                attendance_role=participant.attendance_role,
                speaker_position=participant.speaker_position,
                speaker_role=participant.speaker_role,
                affiliation=participant.affiliation,
                has_spoken=participant.has_spoken,
                speech_count=participant.speech_count,
            )
            for participant in participants
        ]
