from dataclasses import replace
from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from kokkai.domain.repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from kokkai.domain.service.affiliation_import import AffiliationImportService
from kokkai.domain.service.affiliation_timeline import AffiliationTimelineService
from kokkai.domain.valueobject.meeting import MeetingSearchResult
from kokkai.models import AffiliationObservation, ObservedPerson
from kokkai.test_participant import participant_meeting_record


class AffiliationObservationRepositoryTests(TestCase):
    def setUp(self):
        self.record = participant_meeting_record()
        self.repository = AffiliationObservationRepository()

    def test_refresh_groups_speeches_without_using_roleplay_meetings(self):
        """
        シナリオ:
        - 入力: 同一人物が同じ会議で同一会派として複数回発言した公式API会議録。
        - 処理: 会派観測を会議録ID単位で二度生成する。
        - 期待値: ロープレ用Meetingを作らず、人物・日付・会派ごとに1観測へ集約する。
        """
        self.repository.refresh_for_record(self.record)
        self.repository.refresh_for_record(self.record)

        observation = AffiliationObservation.objects.get(
            person__name="藤丸敏",
            affiliation="会派A",
        )

        self.assertEqual(AffiliationObservation.objects.count(), 3)
        self.assertIsNone(observation.meeting)
        self.assertEqual(observation.observed_on, date(2024, 1, 26))
        self.assertEqual(observation.get_source_type_display(), "発言")
        self.assertEqual(observation.speech_count, 2)
        self.assertEqual(observation.evidences.count(), 2)
        self.assertEqual(observation.person.name_yomi, "ふじまるさとし")
        self.assertTrue(
            observation.evidences.filter(
                source_speech_id="121305254X00120240126_001"
            ).exists()
        )
        self.assertTrue(
            AffiliationObservation.objects.filter(
                person__name="石破茂",
                affiliation="会派B",
            ).exists()
        )

    def test_timeline_counts_observed_affiliation_change_without_inferring_gap(self):
        self.repository.refresh_for_record(self.record)
        second_speech = replace(
            self.record.speech_records[1],
            speech_id="121305254X00220240220_001",
            speaker_group="会派B",
            speech="発言本文",
            speech_url="https://kokkai.ndl.go.jp/txt/121305254X00220240220/1",
        )
        second_record = replace(
            self.record,
            issue_id="121305254X00220240220",
            date="2024-02-20",
            meeting_url="https://kokkai.ndl.go.jp/txt/121305254X00220240220",
            speech_records=[second_speech],
        )
        self.repository.refresh_for_record(second_record)

        person = ObservedPerson.objects.get(name="藤丸敏", name_yomi="ふじまるさとし")
        summary, periods = AffiliationTimelineService().get_timeline(person)

        self.assertEqual(summary.observation_count, 2)
        self.assertEqual(summary.speech_count, 3)
        self.assertEqual(summary.affiliation_count, 2)
        self.assertEqual(summary.affiliation_change_count, 1)
        self.assertEqual([period.affiliation for period in periods], ["会派A", "会派B"])
        self.assertEqual(periods[0].last_observed_on, date(2024, 1, 26))
        self.assertEqual(periods[1].first_observed_on, date(2024, 2, 20))


class AffiliationImportServiceTests(TestCase):
    def test_import_period_reads_every_api_page_and_refreshes_each_record(self):
        first_record = participant_meeting_record()
        second_record = replace(first_record, issue_id="121305254X00220240127")
        client = Mock()
        client.search_meetings.side_effect = [
            MeetingSearchResult(2, 1, 1, 2, [first_record]),
            MeetingSearchResult(2, 1, 2, None, [second_record]),
        ]
        repository = Mock()

        with patch("kokkai.domain.service.affiliation_import.sleep"):
            result = AffiliationImportService(client, repository).import_period(
                date(2016, 1, 1), date(2016, 12, 31)
            )

        self.assertEqual(result.meeting_count, 2)
        self.assertEqual(repository.refresh_for_record.call_count, 2)
        self.assertEqual(client.search_meetings.call_count, 2)


class AffiliationTraceabilityViewTests(TestCase):
    def setUp(self):
        self.person = ObservedPerson.objects.create(
            name="議員A", name_yomi="ぎいんえー"
        )
        observation = AffiliationObservation.objects.create(
            person=self.person,
            observed_on=date(2024, 1, 26),
            affiliation="会派A",
            source_meeting_id="121305254X00120240126",
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
        )
        observation.evidences.create(
            source_speech_id="121305254X00120240126_001",
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240126/1",
            source_text="発言本文",
            speech_order=1,
        )

    def test_top_page_and_traceability_page_are_independent_from_roleplay(self):
        home_response = self.client.get(reverse("home:index"))
        traceability_response = self.client.get(
            reverse("kokkai:affiliation_traceability")
        )
        timeline_response = self.client.get(
            reverse("kokkai:politician_timeline", args=[self.person.pk])
        )

        self.assertContains(home_response, "政治家の会派トレーサビリティ")
        self.assertContains(traceability_response, "ロープレとは独立して")
        self.assertContains(traceability_response, 'value="2016-01-01"')
        self.assertContains(timeline_response, "会派観測タイムライン")
        self.assertContains(timeline_response, "発言 121305254X00120240126_001")

    @patch("kokkai.views.AffiliationImportService")
    def test_period_submission_imports_all_meetings_before_redirecting(
        self, service_class
    ):
        response = self.client.post(
            reverse("kokkai:affiliation_traceability"),
            {"start_date": "2016-01-01", "end_date": "2016-12-31"},
        )

        self.assertRedirects(response, reverse("kokkai:affiliation_traceability"))
        service_class.return_value.import_period.assert_called_once_with(
            date(2016, 1, 1), date(2016, 12, 31)
        )
