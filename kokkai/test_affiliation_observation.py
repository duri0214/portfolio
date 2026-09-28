from datetime import date

from django.test import TestCase
from django.urls import reverse

from kokkai.domain.repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from kokkai.domain.service.affiliation_timeline import AffiliationTimelineService
from kokkai.models import (
    AffiliationObservation,
    Meeting,
    ObservedPerson,
    Speech,
)
from kokkai.test_participant import participant_meeting_record


class AffiliationObservationRepositoryTests(TestCase):
    def setUp(self):
        self.first_meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
        )
        record = participant_meeting_record()
        Speech.objects.bulk_create(
            [
                Speech(
                    meeting=self.first_meeting,
                    speaker_name=speech.speaker,
                    speaker_yomi=speech.speaker_yomi or "",
                    speaker_position=speech.speaker_position or "",
                    speaker_role=speech.speaker_role,
                    speaker_affiliation=speech.speaker_group,
                    speech_text=speech.speech or "",
                    speech_order=speech.speech_order,
                    source_speech_id=speech.speech_id,
                    source_url=speech.speech_url,
                )
                for speech in record.speech_records
                if speech.speaker != "会議録情報"
            ]
        )
        self.repository = AffiliationObservationRepository()

    def test_refresh_groups_same_person_date_and_affiliation_with_speech_evidence(self):
        """
        シナリオ:
        - 入力: 同一人物が同じ会議で同一会派として複数回発言した会議録データ。
        - 処理: 会派観測を会議単位で生成し、再度生成する。
        - 期待値: 人物・日付・会派ごとに1観測へ集約し、全発言URLを根拠として保持する。
        """
        self.repository.refresh_for_meeting(self.first_meeting)
        self.repository.refresh_for_meeting(self.first_meeting)

        observation = AffiliationObservation.objects.get(
            person__name="藤丸敏",
            affiliation="会派A",
        )

        self.assertEqual(AffiliationObservation.objects.count(), 3)
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
        """
        シナリオ:
        - 入力: 異なる会議日に会派A、会派Bとして発言した同名・同よみの参加者。
        - 処理: 会派観測を生成して時系列を集計する。
        - 期待値: 観測上の会派変更を1回と数え、二つの表示区間を返す。
        """
        self.repository.refresh_for_meeting(self.first_meeting)
        second_meeting = Meeting.objects.create(
            meeting_date=date(2024, 2, 20),
            session_number=213,
            house="衆議院",
            committee="予算委員会",
            meeting_number="第2号",
            min_id="121305254X00220240220",
            url="https://kokkai.ndl.go.jp/txt/121305254X00220240220",
        )
        Speech.objects.create(
            meeting=second_meeting,
            speaker_name="藤丸敏",
            speaker_yomi="ふじまるさとし",
            speaker_affiliation="会派B",
            speech_text="発言本文",
            speech_order=1,
            source_speech_id="121305254X00220240220_001",
            source_url=second_meeting.url,
        )
        self.repository.refresh_for_meeting(second_meeting)

        person = ObservedPerson.objects.get(name="藤丸敏", name_yomi="ふじまるさとし")
        summary, periods = AffiliationTimelineService().get_timeline(person)

        self.assertEqual(summary.observation_count, 2)
        self.assertEqual(summary.speech_count, 3)
        self.assertEqual(summary.affiliation_count, 2)
        self.assertEqual(summary.affiliation_change_count, 1)
        self.assertEqual([period.affiliation for period in periods], ["会派A", "会派B"])
        self.assertEqual(periods[0].last_observed_on, date(2024, 1, 26))
        self.assertEqual(periods[1].first_observed_on, date(2024, 2, 20))

    def test_empty_affiliation_is_labeled_as_missing_information(self):
        person = ObservedPerson.objects.create(
            name="会派不明", name_yomi="かいはふめい"
        )
        observation = AffiliationObservation.objects.create(
            person=person,
            meeting=self.first_meeting,
            observed_on=self.first_meeting.meeting_date,
            affiliation="",
            source_meeting_id=self.first_meeting.min_id,
            source_url=self.first_meeting.url,
        )

        self.assertEqual(observation.affiliation_label, "会派情報なし")


class AffiliationObservationViewTests(TestCase):
    def setUp(self):
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
        )
        self.person = ObservedPerson.objects.create(
            name="議員A", name_yomi="ぎいんえー"
        )
        observation = AffiliationObservation.objects.create(
            person=self.person,
            meeting=meeting,
            observed_on=meeting.meeting_date,
            affiliation="会派A",
            source_meeting_id=meeting.min_id,
            source_url=meeting.url,
        )
        observation.evidences.create(
            source_speech_id="121305254X00120240126_001",
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00120240126/1",
            source_text="発言本文",
            speech_order=1,
        )

    def test_list_and_timeline_distinguish_observation_from_party_membership(self):
        list_response = self.client.get(reverse("kokkai:politician_list"))
        timeline_response = self.client.get(
            reverse("kokkai:politician_timeline", args=[self.person.pk])
        )

        self.assertContains(
            list_response, "政党所属、入党日、離党日、未観測期間の所属は示しません。"
        )
        self.assertContains(list_response, "人物同定: 未確認")
        self.assertContains(timeline_response, "会派観測タイムライン")
        self.assertContains(timeline_response, "発言 121305254X00120240126_001")
        self.assertContains(timeline_response, "所属継続を示すものではありません。")
