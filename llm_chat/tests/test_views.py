import io
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.service.completion.riddle import RiddleService
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import ChatLogs, RiddleQuestion
from llm_chat.views import IndexView, RiddleSampleCSVView, RiddleCSVUploadView


class ViewLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", password="password", email="admin@example.com"
        )

    def test_index_view_riddle_active_status(self):
        """
        [シナリオ: Viewにおけるなぞなぞ活性状態判定]
        1. 履歴がない場合: is_riddle_active が False であることを確認
        2. 最新履歴がなぞなぞメッセージ (終了なし) の場合: is_riddle_active が True になることを確認
        3. 最新履歴になぞなぞ終了メッセージが含まれる場合: is_riddle_active が False に戻ることを確認
        """

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        request.session = SessionStore()

        # 1. 履歴なし -> Riddle 非アクティブ
        view = IndexView()
        view.request = request
        context = view.get_context_data()
        self.assertFalse(context["is_riddle_active"])

        # 2. なぞなぞ開始メッセージあり -> Riddle アクティブ
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞを出題します",
            use_case_type=UseCaseType.RIDDLE,
        )
        context = view.get_context_data()
        self.assertTrue(context["is_riddle_active"])

        # 3. なぞなぞ終了メッセージあり -> Riddle 非アクティブ
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"お疲れ様でした。 {RiddleService.RIDDLE_END_MESSAGE}",
            use_case_type=UseCaseType.RIDDLE,
        )
        context = view.get_context_data()
        self.assertFalse(context["is_riddle_active"])

    def test_index_view_initial_use_case_type(self):
        """
        [シナリオ: IndexView の get_initial() による直近ユースケースタイプの取得]
        1. 履歴がない場合: デフォルト値が返ることを確認
        2. 直近の履歴が OpenAI Image の場合: OpenAIImage が返ることを確認
        3. 直近の履歴が なぞなぞ (進行中) の場合: Riddle が返ることを確認
        4. 直近の履歴が なぞなぞ (終了) の場合: 直近の model_name に基づく値が返ることを確認
        """

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        request.session = SessionStore()

        view = IndexView()
        view.request = request

        # 1. 履歴なし -> デフォルトで UseCaseType.OPENAI_GPT_STREAMING
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_GPT_STREAMING)

        # 2. 直近が OpenAI Image
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="Image URL",
            model_name=ModelName.GPT_IMAGE_1_MINI,
            use_case_type=UseCaseType.OPENAI_IMAGE,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_IMAGE)

        # 3. なぞなぞ (進行中)
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞです",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.RIDDLE)

        # 4. なぞなぞ (終了)
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"正解です！ {RiddleService.RIDDLE_END_MESSAGE}",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.RIDDLE)

        # 5. ストリーミングモードの復元
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="Streaming request",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.OPENAI_GPT_STREAMING,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_GPT_STREAMING)

        # 6. RAGモードの復元
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="RAG query",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.OPENAI_RAG,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_RAG)

        # 7. なぞなぞ進行中が最優先 (セッションより優先)
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞです",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now() + timedelta(seconds=1),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.RIDDLE)

    def test_riddle_sample_csv_view(self):
        """
        [シナリオ] サンプルCSVダウンロードリンクにアクセスする
        [期待値] 200 OK が返り、CSV形式で期待通りの内容が含まれていること
        """
        factory = RequestFactory()
        request = factory.get(reverse("llm:riddle_sample_csv"))
        request.user = self.user

        response = RiddleSampleCSVView.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(
            'attachment; filename="riddle_sample.csv"', response["Content-Disposition"]
        )

        content = response.content.decode("utf-8")
        lines = content.strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("はじめは4本足", lines[0])
        self.assertIn("人間", lines[0])
        self.assertIn("私は黒い服を着て", lines[1])
        self.assertIn("たいまつ", lines[1])

    def test_riddle_csv_upload_overwrite(self):
        """
        [シナリオ] CSVをアップロードして、既存の問題を全削除して再投入する。
        """
        # 1. 初期データ作成
        RiddleQuestion.objects.all().delete()
        RiddleQuestion.objects.create(
            order=1,
            question_text="古い問題",
            answer_text="答え1",
        )

        # 2. CSVデータ準備
        csv_content = [
            "1,上書き問題1,新しい答え",
            "2,新規問題2,答え2",
        ]
        request = self._build_csv_upload_request(
            csv_content=csv_content,
            filename="test.csv",
        )

        # 3. 実行
        response = RiddleCSVUploadView.post(request)

        # 4. 検証
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RiddleQuestion.objects.count(), 2)
        self.assertFalse(
            RiddleQuestion.objects.filter(question_text="古い問題").exists()
        )
        q1 = RiddleQuestion.objects.get(order=1)
        self.assertEqual(q1.question_text, "上書き問題1")

    def test_riddle_csv_upload_complex_reorder(self):
        """
        [シナリオ] 順序変更を伴うCSVアップロード
        """
        # 1. 初期データ作成 (1, 2, 3)
        RiddleQuestion.objects.all().delete()
        RiddleQuestion.objects.create(order=1, question_text="Q1", answer_text="A1")
        RiddleQuestion.objects.create(order=2, question_text="Q2", answer_text="A2")
        RiddleQuestion.objects.create(order=3, question_text="Q3", answer_text="A3")

        # 2. CSVデータ準備 (1, 3, 2, 4)
        csv_content = [
            "1,Q1,A1",
            "3,Q3,A3",
            "2,New Q2,New A2",
            "4,New Q4,New A4",
        ]
        request = self._build_csv_upload_request(
            csv_content=csv_content,
            filename="test_complex.csv",
        )

        # 3. 実行
        response = RiddleCSVUploadView.post(request)

        # 4. 検証
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RiddleQuestion.objects.count(), 4)
        questions = RiddleQuestion.objects.all().order_by("order")
        self.assertEqual(questions[1].order, 2)
        self.assertEqual(questions[1].question_text, "New Q2")

    def test_clear_chat_logs_view(self):
        """
        [シナリオ: チャット履歴の全削除]
        1. チャット履歴をいくつか作成する
        2. ClearChatLogsView に POST リクエストを送信する
        3. 期待値:
           - レスポンスが 200 OK であること
           - レスポンスに削除件数が含まれていること
           - 実際にレコードが削除されていること
        """
        user = User.objects.create_user(username="test_user_clear")
        from llm_chat.models import ChatLogs

        ChatLogs.objects.create(user=user, role="USER", content="test1")
        ChatLogs.objects.create(user=user, role="ASSISTANT", content="test2")

        from django.urls import reverse

        response = self.client.post(reverse("llm:clear_chat_logs"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["deleted"], 2)
        self.assertEqual(ChatLogs.objects.count(), 0)

    @staticmethod
    def _create_messages_mock():
        from django.contrib.messages.storage.base import BaseStorage
        from django.test import RequestFactory

        request = RequestFactory().get("/")
        return BaseStorage(request)

    def _build_csv_upload_request(self, csv_content: list[str], filename: str):
        csv_file = io.BytesIO("\n".join(csv_content).encode("utf-8"))
        csv_file.name = filename

        factory = RequestFactory()
        request = factory.post(
            reverse("llm:riddle_csv_upload"),
            {"csv_file": csv_file},
        )
        request.user = self.user
        request.session = SessionStore()
        request._messages = self._create_messages_mock()
        return request
