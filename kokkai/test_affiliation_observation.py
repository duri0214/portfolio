from dataclasses import replace
from datetime import date
from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.urls import reverse

from kokkai.domain.repository.affiliation_observation_repository import (
    AffiliationObservationRepository,
)
from kokkai.domain.service.affiliation_import import AffiliationImportService
from kokkai.domain.service.affiliation_timeline import AffiliationTimelineService
from kokkai.domain.valueobject.affiliation import AffiliationImportPage
from kokkai.domain.valueobject.meeting import MeetingSearchResult
from kokkai.models import (
    AffiliationImportJob,
    AffiliationObservation,
    ObservedPerson,
)
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
        """
        シナリオ:
        - 入力: 同一人物について、異なる会派が記載された二つの会議録
        - 処理: 会派記載を収集してタイムラインを取得する
        - 期待値: 観測された会派変更だけを数え、記載のない期間を補完しない
        """
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
    def test_import_page_refreshes_each_record_in_one_api_page(self):
        """
        シナリオ:
        - 入力: 一ページに含まれる国会会議録APIの検索結果
        - 処理: 月次期間の一ページ分を会派記載として収集する
        - 期待値: 各会議録を一度ずつ更新し、次の取得位置を返す
        """
        first_record = participant_meeting_record()
        second_record = replace(first_record, issue_id="121305254X00220240127")
        client = Mock()
        client.search_meetings.return_value = MeetingSearchResult(
            2, 2, 1, 3, [first_record, second_record]
        )
        repository = Mock()

        result = AffiliationImportService(client, repository).import_page(
            date(2016, 1, 1), date(2016, 1, 31), 1
        )

        self.assertEqual(result.meeting_count, 2)
        self.assertEqual(result.total_meeting_count, 2)
        self.assertEqual(result.next_record_position, 3)
        self.assertEqual(repository.refresh_for_record.call_count, 2)
        client.search_meetings.assert_called_once_with(
            date(2016, 1, 1), date(2016, 1, 31), start_record=1
        )

    def test_first_chunk_end_uses_the_end_of_the_start_month(self):
        """
        シナリオ:
        - 入力: 月の途中から翌月以降までの取得期間
        - 処理: 最初の月次取得期間の終了日を求める
        - 期待値: 開始月の末日で分割する
        """
        chunk_end = AffiliationImportService.first_chunk_end(
            date(2026, 9, 28), date(2026, 11, 1)
        )

        self.assertEqual(chunk_end, date(2026, 9, 30))


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

    def test_kokkai_top_and_traceability_page_are_independent_from_roleplay(self):
        """
        シナリオ:
        - 入力: KOKKAIのトップ、会派トレーサビリティ、政治家タイムラインへのアクセス
        - 処理: 各画面を表示する
        - 期待値: KOKKAIトップから遷移でき、会派記載はロープレの実施と独立して表示される
        """
        kokkai_response = self.client.get(reverse("kokkai:index"))
        traceability_response = self.client.get(
            reverse("kokkai:affiliation_traceability")
        )
        timeline_response = self.client.get(
            reverse("kokkai:politician_timeline", args=[self.person.pk])
        )

        self.assertContains(kokkai_response, "政治家の会派トレーサビリティ")
        self.assertContains(traceability_response, "ロープレとは独立して")
        self.assertContains(traceability_response, "政治家別 会派観測ガントチャート")
        self.assertContains(traceability_response, "affiliation-gantt-bar")
        self.assertContains(
            traceability_response,
            f'value="{date.today().replace(year=date.today().year - 10).isoformat()}"',
        )
        self.assertContains(timeline_response, "会派観測タイムライン")
        self.assertContains(timeline_response, "発言 121305254X00120240126_001")

    def test_period_submission_creates_resumable_monthly_import_job(self):
        """
        シナリオ:
        - 入力: 一年間の開始日と終了日を指定した収集フォーム
        - 処理: 会派トレーサビリティ画面へPOSTする
        - 期待値: 最初の月次期間を持つ再開可能な取得処理を作成する
        """
        response = self.client.post(
            reverse("kokkai:affiliation_traceability"),
            {"start_date": "2016-01-01", "end_date": "2016-12-31"},
        )

        job = AffiliationImportJob.objects.get()
        self.assertRedirects(
            response,
            f"{reverse('kokkai:affiliation_traceability')}?import_job={job.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(job.current_start_date, date(2016, 1, 1))
        self.assertEqual(job.current_end_date, date(2016, 1, 31))

    @patch("kokkai.views.AffiliationImportService")
    def test_import_step_completes_a_monthly_job_one_page_at_a_time(
        self, service_class
    ):
        """
        シナリオ:
        - 入力: 一月分の会議録を対象にした開始待ちの取得処理
        - 処理: 次のAPIページを取得するエンドポイントへPOSTする
        - 期待値: 会議録を積み上げ、完了状態とJSONの進捗を返す
        """
        job = AffiliationImportJob.objects.create(
            start_date=date(2016, 1, 1),
            end_date=date(2016, 1, 31),
            current_start_date=date(2016, 1, 1),
            current_end_date=date(2016, 1, 31),
        )
        service_class.return_value.import_page.return_value = AffiliationImportPage(
            meeting_count=2,
            total_meeting_count=2,
            next_record_position=None,
        )

        response = self.client.post(
            reverse("kokkai:affiliation_import_step", args=[job.pk])
        )

        job.refresh_from_db()
        self.assertEqual(response.json()["processed_meeting_count"], 2)
        self.assertEqual(job.status, AffiliationImportJob.Status.COMPLETED)
        service_class.return_value.import_page.assert_called_once_with(
            date(2016, 1, 1), date(2016, 1, 31), 1
        )

    @patch("kokkai.views.AffiliationImportService")
    def test_import_step_keeps_job_resumable_after_api_timeout(self, service_class):
        """
        シナリオ:
        - 入力: 一月分の会議録を対象にした開始待ちの取得処理
        - 処理: 国会会議録APIのタイムアウト時に次のAPIページを取得する
        - 期待値: 500エラーにせず、取得位置を保った再開待ち状態を返す
        """
        job = AffiliationImportJob.objects.create(
            start_date=date(2016, 1, 1),
            end_date=date(2016, 1, 31),
            current_start_date=date(2016, 1, 1),
            current_end_date=date(2016, 1, 31),
        )
        service_class.return_value.import_page.side_effect = requests.Timeout()

        response = self.client.post(
            reverse("kokkai:affiliation_import_step", args=[job.pk])
        )

        job.refresh_from_db()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(job.status, AffiliationImportJob.Status.FAILED)
        self.assertEqual(job.next_record_position, 1)

    def test_chart_separates_affiliations_observed_on_the_same_day(self):
        """
        シナリオ:
        - 入力: 同一人物に同日観測された異なる二つの会派
        - 処理: 人物別会派ガントチャートの描画データを取得する
        - 期待値: 二つのバーを別の段に配置して、会派の混在を隠さない
        """
        AffiliationObservation.objects.create(
            person=self.person,
            observed_on=date(2024, 1, 26),
            affiliation="会派B",
            source_meeting_id="121305254X00220240126",
            source_url="https://kokkai.ndl.go.jp/txt/121305254X00220240126",
        )

        chart = AffiliationTimelineService().get_chart()

        self.assertIsNotNone(chart)
        row = chart.rows[0]
        self.assertEqual(row.lane_count, 2)
        self.assertEqual(
            {segment.affiliation_label for segment in row.segments}, {"会派A", "会派B"}
        )
