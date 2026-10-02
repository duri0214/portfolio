from collections import defaultdict

from django.db.models import Q

from ...models import (
    AffiliationObservation,
    AffiliationObservationEvidence,
    ObservedPerson,
)
from ..service.participant import normalize_person_name, normalize_text
from ..valueobject.meeting import MEETING_METADATA_SPEAKER_NAME, MeetingRecord


class AffiliationObservationRepository:
    """会議録発言を、会派の時点観測として保存・参照する。"""

    def refresh_for_record(self, record: MeetingRecord) -> None:
        """公式APIの会議録1件から会派観測を洗い替え、根拠を重複なく保存する。"""

        evidences_by_key = defaultdict(list)
        for speech in sorted(record.speech_records, key=lambda item: item.speech_order):
            if speech.speaker == MEETING_METADATA_SPEAKER_NAME:
                continue
            name = normalize_person_name(speech.speaker)
            if not name or not normalize_text(speech.speech):
                continue
            key = (
                name,
                normalize_text(speech.speaker_yomi),
                normalize_text(speech.speaker_group),
            )
            evidences_by_key[key].append(speech)

        AffiliationObservation.objects.filter(
            source_meeting_id=record.issue_id
        ).delete()
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
                    observed_on=record.date_obj,
                    source_type=AffiliationObservation.SourceType.SPEECH,
                    affiliation=affiliation,
                    speaker_position=first_speech.speaker_position or "",
                    speaker_role=first_speech.speaker_role or "",
                    speech_count=len(evidences),
                    source_meeting_id=record.issue_id,
                    source_url=record.meeting_url,
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
                source_meeting_id=record.issue_id
            ).select_related("person")
        }
        models = []
        for key, evidences in evidences_by_key.items():
            observation = observation_by_key[key]
            models.extend(
                AffiliationObservationEvidence(
                    observation=observation,
                    source_speech_id=(
                        evidence.speech_id
                        or f"{record.issue_id}_{evidence.speech_order:03d}"
                    ),
                    source_url=evidence.speech_url,
                    source_text=evidence.speech or "",
                    speech_order=evidence.speech_order,
                    speaker_position=evidence.speaker_position or "",
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
            .prefetch_related("evidences")
            .order_by("observed_on", "source_meeting_id", "affiliation", "pk")
        )

    def list_all(self, query: str = ""):
        """氏名・よみで絞った観測対象の会派観測を時系列で取得する。"""

        observations = AffiliationObservation.objects.select_related("person")
        if query:
            observations = observations.filter(
                Q(person__name__icontains=query) | Q(person__name_yomi__icontains=query)
            )
        return observations.order_by(
            "person__name",
            "person__name_yomi",
            "person_id",
            "observed_on",
            "source_meeting_id",
            "affiliation",
            "pk",
        )
