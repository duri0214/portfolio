from dataclasses import replace
from datetime import date
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
from kokkai.models import Meeting, Speech


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
        self.assertEqual(
            repository.upsert_indexes.call_args_list,
            [call([first_record]), call([second_record])],
        )
        client.fetch_meeting.assert_not_called()
        client.search_meetings.assert_not_called()
        mock_sleep.assert_called_once_with(MeetingIndexService.REQUEST_INTERVAL_SECONDS)


class MeetingRepositoryTests(TestCase):
    def test_upsert_indexes_updates_metadata_without_deleting_speeches(self):
        """
        シナリオ:
        - 入力: 発言を持つ既存会議録と、同じ会議録IDの更新済みメタデータ。
        - 処理: upsert_indexes を呼び出す。
        - 期待値: 会議録は1件のまま更新され、既存発言は削除されないこと。
        """
        meeting = Meeting.objects.create(
            meeting_date=date(2024, 1, 1),
            session_number=212,
            house="参議院",
            committee="旧会議名",
            meeting_number="第9号",
            min_id="121305254X00120240126",
            url="https://example.com/old",
        )
        speech = Speech.objects.create(
            meeting=meeting,
            speaker_name="既存発言者",
            speech_text="保存済みの発言",
            speech_order=1,
        )

        MeetingRepository().upsert_indexes([meeting_index_record()])

        meeting.refresh_from_db()
        self.assertEqual(Meeting.objects.count(), 1)
        self.assertEqual(meeting.meeting_date, date(2024, 1, 26))
        self.assertEqual(meeting.committee, "本会議")
        self.assertEqual(
            meeting.pdf_url, "https://kokkai.ndl.go.jp/img/121305254X00120240126"
        )
        self.assertTrue(Speech.objects.filter(pk=speech.pk).exists())
        self.assertEqual(speech.meeting_id, meeting.pk)


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
        - 入力: PDF URLを含む、本文未取得の会議録メタデータ。
        - 処理: 対象期間を指定してロープレ用の会議録選択画面を表示する。
        - 期待値: 院名、会議名、PDFリンク、本文取得用の選択欄が表示されること。
        """
        Meeting.objects.create(
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

        self.assertNotContains(response, "<th>会議録ID</th>")
        self.assertContains(response, "国会会議録ロープレ")
        self.assertContains(
            response,
            "実際の国会会議を題材に、役割と文脈を意識した学習ゲーム",
        )
        self.assertNotContains(response, "シナリオに使う会議録")
        self.assertContains(response, "衆議院")
        self.assertContains(response, "本会議 第1号")
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
            response, "会議録一覧から、ロープレに使いたい会議録を選択します"
        )
        self.assertContains(
            response,
            "期間を指定し、「カタログを取得」を押します。（期間の目安がつかない場合は、「会議録全量へのリンク」から開催状況を確認します。）",
        )
        self.assertNotContains(response, "<li>期間の目安がつかない場合は")
        self.assertContains(
            response,
            "「本文を取得」を押すと、選択した会議録の本文を取得・保存します",
        )
        self.assertNotContains(response, "選択した会議録の本文を取得</button>")
        self.assertContains(
            response, "取得済みの会議録を再選択すると、本文を再取得できます"
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

        self.assertContains(response, "全文を取得する会議録を選択してください。")
        pipeline_class.assert_not_called()
