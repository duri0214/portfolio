from dataclasses import replace
from datetime import date, datetime, timedelta
from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from kokkai.domain.repository.meeting_repository import MeetingRepository
from kokkai.domain.service.kokkai_api import KokkaiAPIClient
from kokkai.domain.service.meeting_index import MeetingIndexService
from kokkai.domain.service.pipeline import KokkaiPipeline
from kokkai.domain.valueobject.meeting import (
    MeetingIndexRecord,
    MeetingIndexSearchResult,
    MeetingRecord,
    MeetingSearchResult,
    SpeechRecord,
)
from kokkai.models import (
    Meeting,
    MeetingScenario,
    ScenarioActor,
    ScenarioChoice,
    ScenarioPlay,
    ScenarioPlayAnswer,
    ScenarioTurn,
    Speech,
)


def meeting_index_record(issue_id: str = "121305254X00120240126") -> MeetingIndexRecord:
    return MeetingIndexRecord(
        issue_id=issue_id,
        image_kind="会議録",
        search_object=0,
        session=213,
        name_of_house="衆議院",
        name_of_meeting="本会議",
        issue="第1号",
        date="2024-01-26",
        closing=None,
        meeting_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}",
        pdf_url=f"https://kokkai.ndl.go.jp/img/{issue_id}",
    )


def meeting_record(issue_id: str = "121305254X00120240126") -> MeetingRecord:
    speech = SpeechRecord(
        speech_id=f"{issue_id}_000",
        speaker="発言者",
        speaker_yomi=None,
        speaker_group="会派",
        speaker_position=None,
        speaker_role=None,
        speech="○発言者君　発言本文",
        speech_order=0,
        start_page=None,
        create_time="2024-01-26T00:00:00",
        update_time="2024-01-26T00:00:00",
        speech_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}/0",
    )
    return MeetingRecord(
        issue_id=issue_id,
        image_kind="会議録",
        search_object=0,
        session=213,
        name_of_house="衆議院",
        name_of_meeting="本会議",
        issue="第1号",
        date="2024-01-26",
        closing=None,
        speech_records=[speech],
        meeting_url=f"https://kokkai.ndl.go.jp/txt/{issue_id}",
        pdf_url=f"https://kokkai.ndl.go.jp/img/{issue_id}",
    )


class KokkaiAPIClientTests(SimpleTestCase):
    @patch("kokkai.domain.service.kokkai_api.requests.get")
    def test_search_meeting_indexes_uses_lightweight_endpoint(self, mock_get):
        """
        シナリオ:
        - 入力: 1件の会議録メタデータを返す会議単位簡易出力API。
        - 処理: 指定期間で search_meeting_indexes を呼び出す。
        - 期待値: meeting_list を最大100件の設定で呼び、発言本文を持たない索引値を返すこと。
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            "numberOfRecords": 1,
            "numberOfReturn": 1,
            "startRecord": 1,
            "nextRecordPosition": None,
            "meetingRecord": [
                {
                    "issueID": "121305254X00120240126",
                    "imageKind": "会議録",
                    "searchObject": 0,
                    "session": 213,
                    "nameOfHouse": "衆議院",
                    "nameOfMeeting": "本会議",
                    "issue": "第1号",
                    "date": "2024-01-26",
                    "closing": None,
                    "meetingURL": "https://kokkai.ndl.go.jp/txt/121305254X00120240126",
                    "pdfURL": "https://kokkai.ndl.go.jp/img/121305254X00120240126",
                }
            ],
        }
        mock_get.return_value = mock_response

        result = KokkaiAPIClient().search_meeting_indexes(
            date(2024, 1, 26), date(2024, 1, 26)
        )

        self.assertEqual(result.number_of_records, 1)
        self.assertEqual(result.meeting_index_records, [meeting_index_record()])
        mock_get.assert_called_once_with(
            KokkaiAPIClient.MEETING_LIST_URL,
            params={
                "from": "2024-01-26",
                "until": "2024-01-26",
                "startRecord": 1,
                "maximumRecords": 100,
                "recordPacking": "json",
            },
            timeout=30,
        )


class MeetingIndexServiceTests(SimpleTestCase):
    @patch("kokkai.domain.service.meeting_index.sleep")
    def test_create_index_saves_all_pages_without_content_import(self, mock_sleep):
        """
        シナリオ:
        - 入力: 2ページに分かれた会議録メタデータとモックのリポジトリ。
        - 処理: create_index を呼び出す。
        - 期待値: 全ページのメタデータだけを保存し、保存件数2を返すこと。
        """
        first_record = meeting_index_record()
        second_record = meeting_index_record("121305254X00220240126")
        client = Mock()
        client.search_meeting_indexes.side_effect = [
            MeetingIndexSearchResult(2, 1, 1, 2, [first_record]),
            MeetingIndexSearchResult(2, 1, 2, None, [second_record]),
        ]
        repository = Mock()

        indexed_count = MeetingIndexService(client, repository).create_index(
            date(2024, 1, 26), date(2024, 1, 26)
        )

        self.assertEqual(indexed_count, 2)
        self.assertEqual(
            client.search_meeting_indexes.call_args_list,
            [
                call(date(2024, 1, 26), date(2024, 1, 26), 1),
                call(date(2024, 1, 26), date(2024, 1, 26), 2),
            ],
        )
        repository.rebuild_meetings.assert_called_once_with(
            [first_record, second_record]
        )
        client.fetch_meeting.assert_not_called()
        client.search_meetings.assert_not_called()
        mock_sleep.assert_called_once_with(MeetingIndexService.REQUEST_INTERVAL_SECONDS)

    @patch("kokkai.domain.service.meeting_index.sleep")
    def test_create_index_stops_when_page_position_does_not_advance(self, mock_sleep):
        """
        シナリオ:
        - 入力: 次ページ位置が現在位置と同じ会議録メタデータAPI。
        - 処理: create_index を呼び出す。
        - 期待値: 同じページを再取得せず、保存して終了すること。
        """
        record = meeting_index_record()
        client = Mock()
        client.search_meeting_indexes.return_value = MeetingIndexSearchResult(
            1, 1, 1, 1, [record]
        )
        repository = Mock()

        indexed_count = MeetingIndexService(client, repository).create_index(
            date(2024, 1, 26), date(2024, 1, 26)
        )

        self.assertEqual(indexed_count, 1)
        client.search_meeting_indexes.assert_called_once_with(
            date(2024, 1, 26), date(2024, 1, 26), 1
        )
        repository.rebuild_meetings.assert_called_once_with([record])
        mock_sleep.assert_not_called()


class MeetingRepositoryTests(TestCase):
    def test_rebuild_meetings_deletes_existing_contents_before_rebuilding_catalog(self):
        """
        シナリオ:
        - 入力: 発言本文を持つ既存カタログと、新しい検索結果のカタログ情報。
        - 処理: rebuild_meetings を呼び出して検索結果を洗い替える。
        - 期待値: 既存の会議録と発言を削除し、新しい結果だけを保存すること。
        """
        existing_meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 1),
            session_number=212,
            house="衆議院",
            committee="旧委員会",
            meeting_number="第9号",
            min_id="121305254X00120240126",
            url="https://example.com/old",
        )
        speech = Speech.objects.create(
            meeting=existing_meeting,
            speaker_name="既存発言者",
            speech_text="保存済みの発言",
            speech_order=1,
        )

        MeetingRepository().rebuild_meetings([meeting_index_record()])

        self.assertEqual(Meeting.objects.count(), 1)
        new_meeting = Meeting.objects.get(min_id=meeting_index_record().issue_id)
        self.assertEqual(new_meeting.meeting_date, date(2024, 1, 26))
        self.assertEqual(new_meeting.committee, "本会議")
        self.assertFalse(Speech.objects.filter(pk=speech.pk).exists())

    def test_rebuild_meetings_with_no_records_clears_existing_meetings(self):
        """
        シナリオ:
        - 入力: 保存済みの会議録と、検索に成功したが0件だった結果。
        - 処理: rebuild_meetings に空の検索結果を渡す。
        - 期待値: 保存済みの会議録を削除し、一覧を0件にすること。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 1),
            session_number=212,
            house="衆議院",
            committee="旧委員会",
            meeting_number="第9号",
            min_id="121305254X00120240101",
            url="https://example.com/old",
        )

        MeetingRepository().rebuild_meetings([])

        self.assertFalse(Meeting.objects.filter(pk=meeting.pk).exists())
        self.assertEqual(Meeting.objects.count(), 0)

    def test_rebuild_meetings_cascades_existing_scenario_data(self):
        """
        シナリオ:
        - 入力: 発言・シナリオ・プレイまで保存された既存会議録。
        - 処理: rebuild_meetings に空の検索結果を渡す。
        - 期待値: 会議録の洗替えに伴い、紐づくデータも削除されること。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 1),
            session_number=212,
            house="衆議院",
            committee="旧委員会",
            meeting_number="第9号",
            min_id="121305254X00120240101",
            url="https://example.com/old",
        )
        speech = Speech.objects.create(
            meeting=meeting,
            speaker_name="発言者",
            speech_text="保存済みの発言",
            speech_order=1,
        )
        scenario = MeetingScenario.objects.create(
            meeting=meeting,
            version=1,
            source_hash="a" * 64,
            prompt_version="test",
            generator_model="test",
            title="テストシナリオ",
            overview="会議録全体の要約",
            success_label="成功",
            failure_label="失敗",
            judgment_criteria="根拠に沿う",
        )
        actor = ScenarioActor.objects.create(
            scenario=scenario,
            display_order=1,
            name="発言者",
        )
        turn = ScenarioTurn.objects.create(
            scenario=scenario,
            turn_number=1,
            actor=actor,
            dialogue="発言内容",
            evidence_speech=speech,
            evidence_note="根拠",
        )
        play = ScenarioPlay.objects.create(
            scenario=scenario,
            selected_actor=actor,
        )
        choice = ScenarioChoice.objects.create(
            play=play,
            turn=turn,
            choice_number=1,
            text="選択肢",
            is_correct=True,
            rationale="根拠",
        )
        answer = ScenarioPlayAnswer.objects.create(
            play=play,
            turn=turn,
            choice=choice,
        )

        MeetingRepository().rebuild_meetings([])

        self.assertFalse(Meeting.objects.filter(pk=meeting.pk).exists())
        self.assertFalse(Speech.objects.filter(pk=speech.pk).exists())
        self.assertFalse(MeetingScenario.objects.filter(pk=scenario.pk).exists())
        self.assertFalse(ScenarioActor.objects.filter(pk=actor.pk).exists())
        self.assertFalse(ScenarioTurn.objects.filter(pk=turn.pk).exists())
        self.assertFalse(ScenarioPlay.objects.filter(pk=play.pk).exists())
        self.assertFalse(ScenarioChoice.objects.filter(pk=choice.pk).exists())
        self.assertFalse(ScenarioPlayAnswer.objects.filter(pk=answer.pk).exists())


class KokkaiPipelineTests(TestCase):
    def test_import_selected_meetings_fetches_only_selected_ids(self):
        """
        シナリオ:
        - 入力: 同じ会議録IDを重複して選択し、全文取得結果を返すAPIクライアント。
        - 処理: import_selected_meetings を呼び出す。
        - 期待値: 重複を除いた会議録IDだけを全文取得し、本文保存時にRAG登録しないこと。
        """
        selected_record = meeting_record()
        client = Mock()
        client.fetch_meeting.return_value = MeetingSearchResult(
            1, 1, 1, None, [selected_record]
        )
        repository = Mock()
        pipeline = KokkaiPipeline(client, repository)

        imported_count = pipeline.import_selected_meetings(
            [selected_record.issue_id, selected_record.issue_id]
        )

        self.assertEqual(imported_count, 1)
        client.fetch_meeting.assert_called_once_with(selected_record.issue_id)
        repository.replace_meeting_contents.assert_called_once()

    def test_import_excludes_metadata_and_empty_speeches_without_embedding(self):
        """
        シナリオ:
        - 入力: 本文、会議録情報メタデータ、空本文を含む会議録取得結果。
        - 処理: 選択した会議録本文を取り込む。
        - 期待値: 実発言だけをXML由来のNo.で保存し、埋め込み処理を呼ばないこと。
        """
        selected_record = meeting_record()
        source_speech = selected_record.speech_records[0]
        metadata_speech = replace(
            source_speech,
            speaker="会議録情報",
            speech="会議の日時などのメタデータ",
            speech_order=0,
        )
        empty_speech = replace(
            source_speech, speaker="空の発言", speech=None, speech_order=20
        )
        source_speech = replace(source_speech, speech_order=21)
        selected_record = replace(
            selected_record,
            speech_records=[metadata_speech, empty_speech, source_speech],
        )
        client = Mock()
        client.fetch_meeting.return_value = MeetingSearchResult(
            1, 1, 1, None, [selected_record]
        )
        repository = Mock()

        KokkaiPipeline(client, repository).import_selected_meetings(
            [selected_record.issue_id]
        )

        repository.replace_meeting_contents.assert_called_once_with(
            selected_record,
            [(source_speech, 21)],
        )


class IndexViewTests(TestCase):
    def test_index_displays_selectable_meeting_metadata(self):
        """
        シナリオ:
        - 入力: PDF URLを含む、本文未取り込みの会議録メタデータ。
        - 処理: 対象期間を指定してロープレ用の会議録選択画面を表示する。
        - 期待値: 院名、会議名、PDFリンク、本文取り込み用の選択欄が表示されること。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://kokkai.ndl.go.jp/txt/121305254X00120240126",
            pdf_url="https://kokkai.ndl.go.jp/img/121305254X00120240126",
        )

        response = self.client.get(
            reverse("kokkai:index"),
            {"start_date": "2024-01-26", "end_date": "2024-01-26"},
        )
        detail_url = reverse("kokkai:meeting_detail", args=[meeting.pk])

        self.assertNotContains(response, "<th>会議録ID</th>")
        self.assertContains(response, "国会会議録ロープレ")
        self.assertContains(
            response,
            "実際の国会会議を題材に、役割と文脈を意識した学習ゲーム",
        )
        self.assertNotContains(response, "シナリオに使う会議録")
        self.assertContains(response, "衆議院")
        self.assertContains(response, "本会議 第1号")
        self.assertContains(response, "本文未取り込み")
        self.assertContains(
            response,
            f'href="{detail_url}?start_date=2024-01-26&amp;end_date=2024-01-26"',
        )
        self.assertContains(response, "期間内の会議録カタログを取得")
        self.assertContains(response, "会議録全量へのリンク")
        self.assertNotContains(response, "（結果を表示）")
        self.assertNotContains(response, 'data-bs-toggle="tooltip"')
        self.assertNotContains(
            response, "期間内の会議録のタイトルと開催情報を一覧で取得します"
        )
        self.assertContains(response, "カタログを取得中…")
        self.assertContains(response, 'name="meeting_ids"')
        self.assertContains(response, "PDF")
        self.assertContains(response, 'id="index-form"')
        self.assertContains(response, "spinner-border")
        self.assertNotContains(response, 'id="index-loading"')
        self.assertNotContains(response, "rowspan=")
        self.assertContains(
            response, "一覧から、ロープレに使いたい会議録にチェックを入れます"
        )
        self.assertContains(
            response,
            "期間を指定し、「カタログを取得」を押します。会議情報の一覧が表示されます。",
        )
        self.assertNotContains(response, "<li>期間の目安がつかない場合は")
        self.assertContains(
            response,
            "「本文をデータベースに取り込む」を押すと、選択した会議録の発言本文を保存します。PDFは参照リンクから確認できます。",
        )
        self.assertContains(
            response,
            '<button type="submit" class="btn btn-primary">本文をデータベースに取り込む</button>',
        )
        self.assertContains(
            response, "本文取り込み済みの会議録を再選択すると、本文を取り込み直せます。"
        )
        self.assertNotContains(
            response, "カタログの更新は、既に保存した発言やChromaのデータを削除しません"
        )
        content = response.content.decode()
        self.assertLess(
            content.index("使い方:"), content.index("期間内の会議録カタログを取得")
        )
        self.assertLess(
            content.index("期間内の会議録カタログを取得"),
            content.rindex("会議録全量へのリンク"),
        )

    def test_meeting_detail_returns_to_the_selected_catalog_period(self):
        """
        シナリオ:
        - 入力: 期間を指定して表示したカタログに含まれる会議録。
        - 処理: 会議詳細を開き、一覧へ戻るリンクを確認する。
        - 期待値: 一覧へ戻るリンクが、表示中の期間を引き継ぐこと。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://example.com/meeting/1",
        )

        response = self.client.get(
            reverse("kokkai:meeting_detail", args=[meeting.pk]),
            {"start_date": "2024-01-01", "end_date": "2024-01-31"},
        )

        self.assertContains(
            response,
            'href="/kokkai/?start_date=2024-01-01&amp;end_date=2024-01-31"',
        )

    def test_index_shows_saved_meetings_independent_of_search_period(self):
        """
        シナリオ:
        - 入力: 検索期間外を含む、異なる開催日のカタログ情報がDBに保存された一覧表示。
        - 処理: 期間指定なしの初期表示と、期間指定ありの一覧表示を行う。
        - 期待値: 保存済みの会議録を表示し、開始日・終了日は取得条件として独立すること。
        """
        for meeting_date, committee in (
            (date(2024, 1, 26), "本会議"),
            (date(2024, 2, 1), "予算委員会"),
        ):
            Meeting.objects.create(
                meeting_date=meeting_date,
                session_number=213,
                house="衆議院",
                committee=committee,
                meeting_number="第1号",
                min_id=f"121305254X001{meeting_date:%Y%m%d}",
                url=f"https://example.com/meeting/{meeting_date:%Y%m%d}",
            )

        today = datetime.now().date()
        response = self.client.get(reverse("kokkai:index"))

        self.assertContains(response, "本会議 第1号")
        self.assertContains(response, "予算委員会 第1号")
        self.assertEqual(response.context["start_date"], today - timedelta(days=30))
        self.assertEqual(response.context["end_date"], today)

        searched_response = self.client.get(
            reverse("kokkai:index"),
            {"start_date": "2024-01-01", "end_date": "2024-01-31"},
        )

        self.assertContains(searched_response, "本会議 第1号")
        self.assertContains(searched_response, "予算委員会 第1号")

    def test_index_does_not_count_catalog_metadata_as_meeting_contents(self):
        """
        シナリオ:
        - 入力: カタログ情報だけを持ち、会議録情報というメタデータ行が紐づく会議録。
        - 処理: 指定期間の会議録一覧を表示する。
        - 期待値: メタデータ行を本文として数えず、本文未取り込みと表示すること。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 26),
            session_number=213,
            house="衆議院",
            committee="本会議",
            meeting_number="第1号",
            min_id="121305254X00120240126",
            url="https://example.com/meeting/1",
        )
        Speech.objects.create(
            meeting=meeting,
            speaker_name="会議録情報",
            speech_text="会議の日時などのメタデータ",
            speech_order=0,
        )

        response = self.client.get(
            reverse("kokkai:index"),
            {"start_date": "2024-01-26", "end_date": "2024-01-26"},
        )

        self.assertContains(response, "本文未取り込み")
        self.assertNotContains(
            response, 'class="badge text-bg-success">本文取り込み済み</span>'
        )

    def test_index_paginates_meetings_with_native_page_size_options(self):
        """
        シナリオ:
        - 入力: 同じ期間内に31件ある会議録一覧。
        - 処理: 1ページ30件で会議録一覧を表示し、次ページへ移動する。
        - 期待値: Django標準のページングと30・60・120件の表示件数を利用できること。
        """
        for index in range(31):
            Meeting.objects.create(
                meeting_date=date(2024, 1, 26),
                session_number=213,
                house="衆議院",
                committee=f"本会議{index:02d}",
                meeting_number="第1号",
                min_id=f"121305254X{index:03d}20240126",
                url=f"https://example.com/meeting/{index}",
            )

        query = {
            "start_date": "2024-01-26",
            "end_date": "2024-01-26",
            "page_size": "30",
        }
        response = self.client.get(reverse("kokkai:index"), query)

        self.assertEqual(response.context["page_size_options"], (30, 60, 120))
        self.assertEqual(response.context["page_size"], 30)
        self.assertEqual(response.context["paginator"].per_page, 30)
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(len(response.context["meetings_by_date"]), 30)
        self.assertContains(response, "表示件数")
        self.assertContains(response, "30件")
        self.assertContains(response, "60件")
        self.assertContains(response, "120件")
        self.assertContains(response, "次へ")
        self.assertContains(response, "最後へ")
        self.assertNotContains(response, "前へ")
        self.assertNotContains(response, "最初へ")

        second_page = self.client.get(reverse("kokkai:index"), {**query, "page": "2"})

        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(len(second_page.context["meetings_by_date"]), 1)
        self.assertContains(second_page, "前へ")
        self.assertContains(second_page, "最初へ")
        self.assertNotContains(second_page, "次へ")
        self.assertNotContains(second_page, "最後へ")

        sixty_page = self.client.get(
            reverse("kokkai:index"), {**query, "page_size": "60"}
        )
        self.assertEqual(sixty_page.context["paginator"].per_page, 60)

    @patch("kokkai.views.MeetingIndexService")
    def test_create_index_with_no_results_shows_period_guidance(self, service_class):
        """
        シナリオ:
        - 入力: 指定期間の索引作成が0件を返す画面リクエスト。
        - 処理: 索引作成フォームを送信する。
        - 期待値: 全文取得処理を行わず、期間変更を案内するメッセージを表示すること。
        """
        service_class.return_value.create_index.return_value = 0

        response = self.client.post(
            reverse("kokkai:index"),
            {
                "action": "create_index",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
            follow=True,
        )

        self.assertContains(
            response, "指定期間に議事録はありません。期間を変更して再度お試しください。"
        )
        service_class.return_value.create_index.assert_called_once_with(
            date(2024, 1, 1), date(2024, 1, 1)
        )

    @patch("kokkai.views.MeetingIndexService")
    def test_create_index_success_does_not_show_completion_flash(self, service_class):
        """
        シナリオ:
        - 入力: 指定期間の索引作成が674件を返す画面リクエスト。
        - 処理: 索引作成フォームを送信する。
        - 期待値: 完了件数のフラッシュメッセージを表示せず、一覧だけを更新すること。
        """
        service_class.return_value.create_index.return_value = 674

        response = self.client.post(
            reverse("kokkai:index"),
            {
                "action": "create_index",
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
            },
            follow=True,
        )

        self.assertNotContains(response, "674件の会議録メタデータを索引化しました。")
        service_class.return_value.create_index.assert_called_once_with(
            date(2024, 1, 1), date(2024, 1, 31)
        )

    @patch("kokkai.views.KokkaiPipeline")
    def test_fetch_selected_without_selection_does_not_import_contents(
        self, pipeline_class
    ):
        """
        シナリオ:
        - 入力: 会議録IDを選択していない本文取得フォームの送信。
        - 処理: fetch_selected アクションを実行する。
        - 期待値: 全文取得パイプラインを起動せず、選択を促すメッセージを表示すること。
        """
        response = self.client.post(
            reverse("kokkai:index"),
            {
                "action": "fetch_selected",
                "start_date": "2024-01-01",
                "end_date": "2024-01-01",
            },
            follow=True,
        )

        self.assertContains(
            response,
            "本文をデータベースに取り込む会議録を選択してください。",
        )
        pipeline_class.assert_not_called()
