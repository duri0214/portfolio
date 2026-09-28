from collections import defaultdict

from ...models import (
    AffiliationObservation,
    AffiliationObservationEvidence,
    Meeting,
    ObservedPerson,
    Speech,
)
from ..service.participant import normalize_person_name, normalize_text


class AffiliationObservationRepository:
    """会議録発言を、会派の時点観測として保存・参照する。"""

    def refresh_for_meeting(self, meeting: Meeting) -> None:
        """会議単位で会派観測を洗い替え、発言根拠を重複なく保存する。"""

        evidences_by_key = defaultdict(list)
        source_speeches = (
            Speech.objects.filter(meeting=meeting)
            .exclude(speaker_name="会議録情報")
            .order_by("speech_order", "pk")
        )
        for speech in source_speeches:
            name = normalize_person_name(speech.speaker_name)
            if not name or not normalize_text(speech.speech_text):
                continue
            key = (
                name,
                normalize_text(speech.speaker_yomi),
                normalize_text(speech.speaker_affiliation),
            )
            evidences_by_key[key].append(speech)

        AffiliationObservation.objects.filter(meeting=meeting).delete()
        if not evidences_by_key:
            return

        observations = []
        for (name, name_yomi, affiliation), evidences in evidences_by_key.items():
            person, _ = ObservedPerson.objects.get_or_create(
                name=name,
                name_yomi=name_yomi,
            )
            first_speech = evidences[0]
            observations.append(
                AffiliationObservation(
                    person=person,
                    meeting=meeting,
                    observed_on=meeting.meeting_date,
                    source_type=AffiliationObservation.SourceType.SPEECH,
                    affiliation=affiliation,
                    speaker_position=first_speech.speaker_position,
                    speaker_role=first_speech.speaker_role or "",
                    speech_count=len(evidences),
                    source_meeting_id=meeting.min_id,
                    source_url=meeting.url,
                )
            )
        AffiliationObservation.objects.bulk_create(observations)

        observation_by_key = {
            (
                observation.person.name,
                observation.person.name_yomi,
                observation.affiliation,
            ): observation
            for observation in AffiliationObservation.objects.filter(
                meeting=meeting
            ).select_related("person")
        }
        models = []
        for key, evidences in evidences_by_key.items():
            observation = observation_by_key[key]
            models.extend(
                AffiliationObservationEvidence(
                    observation=observation,
                    source_speech_id=(
                        evidence.source_speech_id
                        or f"{meeting.min_id}_{evidence.speech_order:03d}"
                    ),
                    source_url=evidence.source_url,
                    source_text=evidence.speech_text,
                    speech_order=evidence.speech_order,
                    speaker_position=evidence.speaker_position,
                    speaker_role=evidence.speaker_role or "",
                )
                for evidence in evidences
            )
        AffiliationObservationEvidence.objects.bulk_create(models)

    def list_people(self):
        """会派観測が1件以上ある観測対象を、観測順に取得する。"""

        return ObservedPerson.objects.filter(
            affiliation_observations__isnull=False
        ).distinct()

    def list_for_person(self, person: ObservedPerson):
        """観測対象の会派観測と一次資料根拠を時系列で取得する。"""

        return (
            AffiliationObservation.objects.filter(person=person)
            .select_related("meeting")
            .prefetch_related("evidences")
            .order_by("observed_on", "meeting__min_id", "affiliation", "pk")
        )
