from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, Client
from django.urls import reverse

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.repository.completion.rokunohe_minutes import (
    RokunoheMinutesRagRepository,
)
from llm_chat.domain.repository.completion.rokunohe_minutes_theme import (
    RokunoheMinuteThemeAnalysisRepository,
)
from llm_chat.domain.service.completion.rokunohe_minutes import (
    RokunoheMinuteThemeAnalysisService,
    RokunoheMinutesPdfImportService,
    RokunoheMinutesRagService,
)
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    ROKUNOHE_MINUTES_COLLECTION_NAME,
    RokunoheMinuteThemeChunkAnalysis,
    RokunoheMinuteThemeClusterAnalysis,
    RokunoheMinutesCollectionItem,
    RokunoheMinutesImportStatus,
    RokunoheMinutesPdf,
    RokunoheMinutesThemeSourceChunk,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import ChatLogs, RokunoheMinuteThemeAnalysisJob


class RokunoheMinutesRagViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username="testuser", email="test@example.com", password="password"
        )
        self.client.login(username="testuser", password="password")

    def test_rokunohe_minutes_get(self):
        """GETリクエストで画面が表示されること"""
        response = self.client.get(reverse("llm:rokunohe_minutes"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "llm_chat/rokunohe_minutes.html")
        self.assertIn("form", response.context)
        self.assertEqual(
            response.context["use_case_type"], UseCaseType.ROKUNOHE_MINUTES_RAG
        )

    @patch(
        "llm_chat.domain.use_case.completion.rokunohe_minutes.RokunoheMinutesRagUseCase.execute"
    )
    def test_rokunohe_minutes_post_success(self, mock_execute):
        """POSTリクエストでRAG回答が返されること"""
        # モックの設定
        mock_message = MessageDTO(
            role=RoleType.ASSISTANT,
            content="これはテストの回答です。",
            user=self.user,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        mock_execute.return_value = mock_message

        response = self.client.post(
            reverse("llm:rokunohe_minutes"),
            {"user_input": "六戸町の予算について教えて"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["content"], "これはテストの回答です。")
        mock_execute.assert_called_once()

    @patch(
        "llm_chat.domain.use_case.completion.rokunohe_minutes.RokunoheMinutesRagUseCase.execute"
    )
    def test_rokunohe_minutes_post_anonymous(self, mock_execute):
        """未ログイン状態でのPOSTリクエストがデフォルトユーザーとして処理されること"""
        self.client.logout()
        # デフォルトユーザー (pk=1) が必要
        if not User.objects.filter(pk=1).exists():
            User.objects.create(pk=1, username="default_user")
        default_user = User.objects.get(pk=1)

        # モックの設定
        mock_message = MessageDTO(
            role=RoleType.ASSISTANT,
            content="匿名回答",
            user=default_user,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        mock_execute.return_value = mock_message

        response = self.client.post(
            reverse("llm:rokunohe_minutes"),
            {"user_input": "こんにちは"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["result"]["content"], "匿名回答")
        # デフォルトユーザーが使われていることを検証
        self.assertEqual(mock_execute.call_args[1]["user"], default_user)

    def test_clear_chat_logs_with_use_case(self):
        """特定のユースケースのみが削除されること"""
        from llm_chat.models import ChatLogs

        # ダミーデータの作成
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="q1",
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="q2",
            use_case_type=UseCaseType.OPENAI_GPT,
        )

        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 2)

        response = self.client.post(
            reverse("llm:clear_chat_logs"),
            {"use_case_type": UseCaseType.ROKUNOHE_MINUTES_RAG},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            ChatLogs.objects.filter(
                user=self.user, use_case_type=UseCaseType.OPENAI_GPT
            ).count(),
            1,
        )


class RokunohePdfDownloadViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_superuser_can_start_pdf_download(self):
        """
        シナリオ:
        - 入力: superuserでログインした状態。
        - 処理: 六戸町会議録PDF取得・ベクトル化ボタンのPOST先へリクエストする。
        - 期待値: 管理コマンドが呼び出され、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        summary_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content="取り込み後の初回サマリーです。",
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        ChatLogs.objects.create(
            user=user,
            role=RoleType.USER.value,
            content="古い質問",
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        with patch("llm_chat.views.call_command") as call_command_mock, patch(
            "llm_chat.views.RokunoheMinutesRagService"
        ) as rag_service_mock:
            rag_service_mock.return_value.generate_initial_summary.return_value = (
                summary_message
            )
            response = self.client.post(
                reverse("llm:rokunohe_pdf_download"),
                {"reset_consent": "1"},
            )

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        call_command_mock.assert_called_once_with("rokunohe_pdf_download")
        rag_service_mock.return_value.generate_initial_summary.assert_called_once_with(
            user
        )
        self.assertEqual(
            list(
                ChatLogs.objects.filter(
                    user=user,
                    use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
                ).values_list("content", flat=True)
            ),
            ["取り込み後の初回サマリーです。"],
        )

    def test_superuser_must_consent_to_reset_before_pdf_download(self):
        """
        シナリオ:
        - 入力: superuserだが会話リセット同意値なしでPOSTする。
        - 処理: 六戸町会議録PDF取得・ベクトル化ボタンのPOST先へリクエストする。
        - 期待値: 管理コマンドを呼び出さず、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin-consent",
            email="admin-consent@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch("llm_chat.views.call_command") as call_command_mock, patch(
            "llm_chat.views.RokunoheMinutesRagService"
        ) as rag_service_mock:
            response = self.client.post(reverse("llm:rokunohe_pdf_download"))

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        call_command_mock.assert_not_called()
        rag_service_mock.assert_not_called()

    def test_non_superuser_cannot_start_pdf_download(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: 六戸町会議録PDF取得・ベクトル化ボタンのPOST先へリクエストする。
        - 期待値: 403が返り、管理コマンドは呼び出されないこと。
        """
        user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch("llm_chat.views.call_command") as call_command_mock:
            # raise_exception=True なので PermissionDenied が発生するはずだが、
            # TestClient はデフォルトでそれを 403 レスポンスとして処理する（あるいは例外を上げる）
            # ここではレスポンスコードをチェック
            response = self.client.post(reverse("llm:rokunohe_pdf_download"))

        self.assertEqual(403, response.status_code)
        call_command_mock.assert_not_called()

    def test_superuser_redirects_when_pdf_download_is_already_running(self):
        """
        シナリオ:
        - 入力: superuserでログインし、PDF保存処理が既に実行中の状態。
        - 処理: 六戸町会議録PDF取得・ベクトル化ボタンのPOST先へリクエストする。
        - 期待値: 例外で500にせず、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch(
            "llm_chat.views.call_command",
            side_effect=CommandError("六戸町PDFダウンロードは既に実行中です。"),
        ), patch("llm_chat.views.RokunoheMinutesRagService") as rag_service_mock:
            response = self.client.post(
                reverse("llm:rokunohe_pdf_download"),
                {"reset_consent": "1"},
            )

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        rag_service_mock.assert_not_called()

    def test_superuser_sees_pdf_download_button(self):
        """
        シナリオ:
        - 入力: superuserでログインした状態。
        - 処理: 六戸町会議録QAページを表示する。
        - 期待値: 会議録PDF取得・ベクトル化ボタンが有効な状態で表示されること。
        """
        user = User.objects.create_superuser(
            username="admin3",
            email="admin3@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("llm:rokunohe_minutes"))

        self.assertContains(response, "会議録PDF取得・ベクトル化")
        self.assertContains(response, "コレクションリセット")
        self.assertContains(response, "テーマ分析を実行")
        self.assertContains(response, "コレクションビューア")
        self.assertContains(response, 'class="btn btn-outline-success btn-sm"')

    def test_non_superuser_sees_disabled_admin_buttons(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: 六戸町会議録QAページを表示する。
        - 期待値: 管理者向け操作ボタンが無効な状態で表示されること。
        """
        user = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("llm:rokunohe_minutes"))

        self.assertContains(response, "会議録PDF取得・ベクトル化")
        self.assertContains(response, "管理者権限が必要なボタンは無効化されています")
        self.assertContains(response, "disabled")
        self.assertContains(response, "コレクションリセット")
        self.assertContains(response, "テーマ分析を実行")
        self.assertContains(response, "コレクションビューア")

    @patch("llm_chat.views.RokunoheMinutesRagRepository")
    def test_superuser_can_reset_vector_db_collection(self, mock_repository):
        """
        シナリオ:
        - 入力: superuserでログインし、六戸町会議録RAG履歴がある状態。
        - 処理: Vector DBコレクションリセットのPOST先へ同意値付きでリクエストする。
        - 期待値: コレクションがリセットされ、六戸町会議録RAG履歴も削除されること。
        """
        user = User.objects.create_superuser(
            username="admin-reset",
            email="admin-reset@example.com",
            password="password",
        )
        self.client.force_login(user)
        ChatLogs.objects.create(
            user=user,
            role=RoleType.USER.value,
            content="古い質問",
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        mock_repository.return_value.reset_collection.return_value = 3

        response = self.client.post(
            reverse("llm:rokunohe_vector_db_reset"),
            {"reset_collection_consent": "1"},
        )

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        mock_repository.return_value.reset_collection.assert_called_once_with()
        self.assertFalse(
            ChatLogs.objects.filter(
                user=user,
                use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
            ).exists()
        )

    @patch("llm_chat.views.RokunoheMinutesRagRepository")
    def test_superuser_must_consent_to_reset_vector_db_collection(
        self, mock_repository
    ):
        """
        シナリオ:
        - 入力: superuserだが同意値なしでPOSTする。
        - 処理: Vector DBコレクションリセットのPOST先へリクエストする。
        - 期待値: コレクションリセットを呼び出さず、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin-reset-consent",
            email="admin-reset-consent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("llm:rokunohe_vector_db_reset"))

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        mock_repository.assert_not_called()

    def test_non_superuser_cannot_reset_vector_db_collection(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: Vector DBコレクションリセットのPOST先へリクエストする。
        - 期待値: 403が返ること。
        """
        user = User.objects.create_user(
            username="user-reset",
            email="user-reset@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("llm:rokunohe_vector_db_reset"),
            {"reset_collection_consent": "1"},
        )

        self.assertEqual(403, response.status_code)

    @patch("llm_chat.views.RokunoheMinuteThemeAnalysisService")
    def test_superuser_can_run_theme_analysis(self, mock_service):
        """
        シナリオ:
        - 入力: superuserでログインし、テーマ分析実行へ同意した状態。
        - 処理: テーマ分析実行のPOST先へリクエストする。
        - 期待値: テーマ分析Serviceが呼び出され、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin-theme",
            email="admin-theme@example.com",
            password="password",
        )
        self.client.force_login(user)
        mock_job = Mock(chunk_count=20, actual_cluster_count=5)
        mock_service.return_value.run.return_value = mock_job

        response = self.client.post(
            reverse("llm:rokunohe_theme_analysis_run"),
            {"analysis_consent": "1"},
        )

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        mock_service.return_value.run.assert_called_once_with()

    @patch("llm_chat.views.RokunoheMinuteThemeAnalysisService")
    def test_superuser_must_consent_to_run_theme_analysis(self, mock_service):
        """
        シナリオ:
        - 入力: superuserだが同意値なしでPOSTする。
        - 処理: テーマ分析実行のPOST先へリクエストする。
        - 期待値: テーマ分析Serviceを呼び出さず、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin-theme-consent",
            email="admin-theme-consent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("llm:rokunohe_theme_analysis_run"))

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        mock_service.assert_not_called()

    def test_non_superuser_cannot_run_theme_analysis(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: テーマ分析実行のPOST先へリクエストする。
        - 期待値: 403が返ること。
        """
        user = User.objects.create_user(
            username="user-theme",
            email="user-theme@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("llm:rokunohe_theme_analysis_run"),
            {"analysis_consent": "1"},
        )

        self.assertEqual(403, response.status_code)

    @patch("llm_chat.views.RokunoheMinutesRagRepository")
    def test_superuser_can_view_vector_db_collection(self, mock_repository):
        """
        シナリオ:
        - 入力: superuserでログインし、Repositoryがコレクション表示用データを返す状態。
        - 処理: コレクションビューア画面へGETリクエストする。
        - 期待値: 管理者専用画面にChroma ID、メタデータ、本文プレビューが表示されること。
        """
        user = User.objects.create_superuser(
            username="admin-viewer",
            email="admin-viewer@example.com",
            password="password",
        )
        self.client.force_login(user)
        mock_repository.return_value.count_collection_items.return_value = 1
        mock_repository.return_value.list_collection_items.return_value = [
            RokunoheMinutesCollectionItem(
                chroma_id="doc_1",
                source="20260225_会議録.pdf",
                source_date="20260225",
                page=1,
                chunk_index=0,
                preview="本文プレビューです。",
            )
        ]

        response = self.client.get(reverse("llm:rokunohe_collection_viewer"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "llm_chat/rokunohe_collection_viewer.html")
        mock_repository.return_value.count_collection_items.assert_called_once_with(
            source_date_from=None
        )
        mock_repository.return_value.list_collection_items.assert_called_once_with(
            limit=100,
            offset=0,
            source_date_from=None,
        )
        self.assertContains(response, "doc_1")
        self.assertContains(response, "20260225_会議録.pdf")
        self.assertContains(response, "20260225")
        self.assertContains(response, "本文プレビューです。")
        self.assertContains(response, "全 1 件中 1-1 件")

    @patch("llm_chat.views.RokunoheMinutesRagRepository")
    def test_collection_viewer_uses_page_and_per_page(self, mock_repository):
        """
        シナリオ:
        - 入力: superuserでログインし、2ページ目と50件表示を指定する。
        - 処理: コレクションビューア画面へGETリクエストする。
        - 期待値: Repositoryへlimit=50、offset=50が渡され、ページ情報が表示されること。
        """
        user = User.objects.create_superuser(
            username="admin-viewer-page",
            email="admin-viewer-page@example.com",
            password="password",
        )
        self.client.force_login(user)
        mock_repository.return_value.count_collection_items.return_value = 120
        mock_repository.return_value.list_collection_items.return_value = [
            RokunoheMinutesCollectionItem(
                chroma_id="doc_51",
                source="20260225_会議録.pdf",
                source_date="20260225",
                page=3,
                chunk_index=2,
                preview="51件目です。",
            )
        ]

        response = self.client.get(
            reverse("llm:rokunohe_collection_viewer"),
            {"page": "2", "per_page": "50"},
        )

        self.assertEqual(response.status_code, 200)
        mock_repository.return_value.list_collection_items.assert_called_once_with(
            limit=50,
            offset=50,
            source_date_from=None,
        )
        self.assertContains(response, "全 120 件中 51-51 件")
        self.assertContains(response, "2 / 3")
        self.assertContains(response, "doc_51")

    @patch("llm_chat.views.timezone.localdate")
    @patch("llm_chat.views.RokunoheMinutesRagRepository")
    def test_collection_viewer_uses_recent_year_query_type(
        self, mock_repository, mock_localdate
    ):
        """
        シナリオ:
        - 入力: superuserでログインし、クエリタイプに直近1年を指定する。
        - 処理: コレクションビューア画面へGETリクエストする。
        - 期待値: 1年前の日付を下限としてRepositoryへ渡し、直近1年表示になること。
        """
        mock_localdate.return_value = date(2026, 6, 12)
        user = User.objects.create_superuser(
            username="admin-viewer-recent",
            email="admin-viewer-recent@example.com",
            password="password",
        )
        self.client.force_login(user)
        mock_repository.return_value.count_collection_items.return_value = 1
        mock_repository.return_value.list_collection_items.return_value = [
            RokunoheMinutesCollectionItem(
                chroma_id="doc_recent",
                source="20260225_会議録.pdf",
                source_date="20260225",
                page=1,
                chunk_index=0,
                preview="直近1年の本文です。",
            )
        ]

        response = self.client.get(
            reverse("llm:rokunohe_collection_viewer"),
            {"query_type": "recent_year", "per_page": "50"},
        )

        self.assertEqual(response.status_code, 200)
        mock_repository.return_value.count_collection_items.assert_called_once_with(
            source_date_from=20250612
        )
        mock_repository.return_value.list_collection_items.assert_called_once_with(
            limit=50,
            offset=0,
            source_date_from=20250612,
        )
        self.assertContains(response, "直近1年: 全 1 件中 1-1 件")
        self.assertContains(response, "doc_recent")

    def test_non_superuser_cannot_view_vector_db_collection(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: コレクションビューア画面へGETリクエストする。
        - 期待値: 403が返ること。
        """
        user = User.objects.create_user(
            username="user-viewer",
            email="user-viewer@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("llm:rokunohe_collection_viewer"))

        self.assertEqual(403, response.status_code)


class RokunoheMinutesPdfImportServiceTest(TestCase):
    @patch("llm_chat.domain.service.completion.rokunohe_minutes.PdfReader")
    def test_imports_pdf_text_to_repository(self, mock_pdf_reader):
        """
        シナリオ:
        - 入力: 未登録のPDFと、PDFから抽出できるテキスト。
        - 処理: PDFインポートサービスを実行する。
        - 期待値: PDF本文と出典メタデータを持つドキュメントがRepositoryへ登録されること。
        """
        repository = Mock()
        repository.exists.return_value = False
        mock_page = Mock()
        mock_page.extract_text.return_value = "六戸町会議録の内容です。"
        mock_pdf_reader.return_value.pages = [mock_page]

        service = RokunoheMinutesPdfImportService(repository=repository)
        status = service.import_pdf(Path("会議録.pdf"))

        self.assertEqual(status, RokunoheMinutesImportStatus.IMPORTED)
        repository.delete_pdf_documents.assert_called_once()
        repository.upsert_documents.assert_called_once()
        docs = repository.upsert_documents.call_args[0][0]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "六戸町会議録の内容です。")
        self.assertEqual(docs[0].metadata["source"], "会議録.pdf")
        self.assertEqual(docs[0].metadata["id"], "rokunohe_会議録_page_1")
        self.assertEqual(docs[0].metadata["page"], 1)
        self.assertEqual(docs[0].metadata["chunk_index"], 0)

    @patch("llm_chat.domain.service.completion.rokunohe_minutes.PdfReader")
    def test_imports_pdf_text_with_source_date_metadata(self, mock_pdf_reader):
        """
        シナリオ:
        - 入力: ファイル名先頭に日付を持つPDF。
        - 処理: PDFインポートサービスを実行する。
        - 期待値: ファイル名の日付がメタデータへ登録されること。
        """
        repository = Mock()
        repository.exists.return_value = False
        mock_page = Mock()
        mock_page.extract_text.return_value = "日付付き会議録の内容です。"
        mock_pdf_reader.return_value.pages = [mock_page]

        service = RokunoheMinutesPdfImportService(repository=repository)
        status = service.import_pdf(Path("20260225_会議録.pdf"))

        self.assertEqual(status, RokunoheMinutesImportStatus.IMPORTED)
        docs = repository.upsert_documents.call_args[0][0]
        self.assertEqual(docs[0].metadata["source_date"], "20260225")
        self.assertEqual(docs[0].metadata["source_date_ymd"], 20260225)

    @patch("llm_chat.domain.service.completion.rokunohe_minutes.PdfReader")
    def test_skips_existing_pdf_before_reading(self, mock_pdf_reader):
        """
        シナリオ:
        - 入力: Repositoryで登録済みと判定されるPDF。
        - 処理: PDFインポートサービスを実行する。
        - 期待値: PDF読み取りと登録を行わず、登録済みスキップ結果が返ること。
        """
        repository = Mock()
        repository.exists.return_value = True

        service = RokunoheMinutesPdfImportService(repository=repository)
        status = service.import_pdf(Path("登録済み.pdf"))

        self.assertEqual(status, RokunoheMinutesImportStatus.SKIPPED_EXISTING)
        mock_pdf_reader.assert_not_called()
        repository.delete_pdf_documents.assert_not_called()
        repository.upsert_documents.assert_not_called()

    @patch("llm_chat.domain.service.completion.rokunohe_minutes.PdfReader")
    def test_skips_pdf_when_text_is_empty(self, mock_pdf_reader):
        """
        シナリオ:
        - 入力: 未登録だが本文を抽出できないPDF。
        - 処理: PDFインポートサービスを実行する。
        - 期待値: Repositoryへ登録せず、本文なしスキップ結果が返ること。
        """
        repository = Mock()
        repository.exists.return_value = False
        mock_page = Mock()
        mock_page.extract_text.return_value = ""
        mock_pdf_reader.return_value.pages = [mock_page]

        service = RokunoheMinutesPdfImportService(repository=repository)
        status = service.import_pdf(Path("空.pdf"))

        self.assertEqual(status, RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT)
        repository.delete_pdf_documents.assert_not_called()
        repository.upsert_documents.assert_not_called()


class RokunoheMinutesRagServiceTest(TestCase):
    def test_generate_uses_repository_answer(self):
        """
        シナリオ:
        - 入力: RepositoryがRAG回答を返す状態のユーザーメッセージ。
        - 処理: 六戸町会議録RAGサービスで回答を生成する。
        - 期待値: Repositoryの回答内容を使ったassistantメッセージが返ること。
        """
        user = User.objects.create_user(username="rag-user")
        repository = Mock()
        repository.retrieve_answer.return_value = Mock(answer="六戸町の回答です。")
        service = RokunoheMinutesRagService(repository=repository)
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content="質問です",
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )

        assistant_message = service.generate(user_message)

        repository.retrieve_answer.assert_called_once()
        self.assertEqual(assistant_message.content, "六戸町の回答です。")
        self.assertEqual(
            assistant_message.use_case_type,
            UseCaseType.ROKUNOHE_MINUTES_RAG,
        )


class RokunoheMinuteThemeAnalysisServiceTest(TestCase):
    def test_run_saves_llm_labels_and_kmeans_clusters(self):
        """
        シナリオ:
        - 入力: embedding付きの六戸町会議録チャンク2件と、LLMラベルServiceのモック。
        - 処理: テーマ分析Serviceを実行する。
        - 期待値: 候補ラベル抽出、K-meansクラスタリング、DB保存Repository呼び出しが行われること。
        """
        rag_repository = Mock()
        rag_repository.list_theme_source_chunks.return_value = [
            RokunoheMinutesThemeSourceChunk(
                chroma_id="doc_1",
                document="学校給食についての議論です。",
                source="20260225_会議録.pdf",
                source_date="20260225",
                page=1,
                chunk_index=0,
                embedding=[0.0, 0.0],
            ),
            RokunoheMinutesThemeSourceChunk(
                chroma_id="doc_2",
                document="道路整備についての議論です。",
                source="20260301_会議録.pdf",
                source_date="20260301",
                page=2,
                chunk_index=1,
                embedding=[10.0, 10.0],
            ),
        ]
        theme_repository = Mock()
        job = Mock()
        theme_repository.create_job.return_value = job
        theme_repository.mark_completed.return_value = job
        label_service = Mock()
        label_service.model_name = "gpt-5-mini"
        label_service.extract_candidate_labels.side_effect = [
            ["学校給食"],
            ["道路整備"],
        ]
        label_service.name_cluster.side_effect = ["学校給食", "道路整備"]
        service = RokunoheMinuteThemeAnalysisService(
            rag_repository=rag_repository,
            theme_repository=theme_repository,
            label_service=label_service,
        )

        result = service.run()

        self.assertEqual(result, job)
        theme_repository.reset_analysis_results.assert_called_once_with()
        theme_repository.create_job.assert_called_once_with(
            requested_cluster_count=50,
            llm_model_name="gpt-5-mini",
        )
        theme_repository.save_analysis_result.assert_called_once()
        clusters = theme_repository.save_analysis_result.call_args.kwargs["clusters"]
        self.assertEqual(len(clusters), 2)
        self.assertEqual(sum(cluster.chunk_count for cluster in clusters), 2)
        theme_repository.mark_completed.assert_called_once_with(
            job=job,
            chunk_count=2,
            actual_cluster_count=2,
        )

    def test_run_raises_when_collection_is_empty(self):
        """
        シナリオ:
        - 入力: Chroma DBの分析対象チャンクが空の状態。
        - 処理: テーマ分析Serviceを実行する。
        - 期待値: 分析ジョブを作成せず、対象なしのValueErrorが発生すること。
        """
        rag_repository = Mock()
        rag_repository.list_theme_source_chunks.return_value = []
        theme_repository = Mock()
        service = RokunoheMinuteThemeAnalysisService(
            rag_repository=rag_repository,
            theme_repository=theme_repository,
            label_service=Mock(),
        )

        with self.assertRaises(ValueError):
            service.run()

        theme_repository.create_job.assert_not_called()


class RokunoheMinuteThemeAnalysisRepositoryTest(TestCase):
    def test_saves_cluster_and_chunk_analysis_result(self):
        """
        シナリオ:
        - 入力: 分析ジョブと、クラスタ1件・チャンク1件の分析結果。
        - 処理: テーマ分析Repositoryで分析結果を保存し、ジョブを完了にする。
        - 期待値: クラスタ集計値とチャンク候補ラベルがDjango DBに保存されること。
        """
        repository = RokunoheMinuteThemeAnalysisRepository()
        job = repository.create_job(
            requested_cluster_count=50,
            llm_model_name="gpt-5-mini",
        )
        source_chunk = RokunoheMinutesThemeSourceChunk(
            chroma_id="doc_1",
            document="学校給食についての議論です。",
            source="20260225_会議録.pdf",
            source_date="20260225",
            page=1,
            chunk_index=0,
            embedding=[0.0, 0.0],
        )
        chunk_analysis = RokunoheMinuteThemeChunkAnalysis(
            source_chunk=source_chunk,
            candidate_labels=["学校給食"],
            cluster_index=0,
        )
        cluster_analysis = RokunoheMinuteThemeClusterAnalysis(
            cluster_index=0,
            label="学校給食",
            representative_chunk_id="doc_1",
            chunks=[chunk_analysis],
        )

        repository.save_analysis_result(job=job, clusters=[cluster_analysis])
        completed_job = repository.mark_completed(
            job=job,
            chunk_count=1,
            actual_cluster_count=1,
        )

        self.assertEqual(
            completed_job.status, RokunoheMinuteThemeAnalysisJob.STATUS_COMPLETED
        )
        cluster = completed_job.clusters.get()
        self.assertEqual(cluster.label, "学校給食")
        self.assertEqual(cluster.chunk_count, 1)
        self.assertEqual(cluster.pdf_count, 1)
        self.assertEqual(cluster.source_date_from, "20260225")
        theme_chunk = completed_job.theme_chunks.get()
        self.assertEqual(theme_chunk.chunk_id, "doc_1")
        self.assertEqual(theme_chunk.candidate_labels, ["学校給食"])

    def test_reset_analysis_results_removes_previous_jobs(self):
        """
        シナリオ:
        - 入力: 既存のテーマ分析ジョブが保存されている状態。
        - 処理: テーマ分析Repositoryで分析結果をリセットする。
        - 期待値: 既存ジョブと紐づくクラスタ・チャンクが削除されること。
        """
        repository = RokunoheMinuteThemeAnalysisRepository()
        old_job = repository.create_job(
            requested_cluster_count=50,
            llm_model_name="gpt-5-mini",
        )
        source_chunk = RokunoheMinutesThemeSourceChunk(
            chroma_id="old_doc",
            document="古い分析結果です。",
            source="20260225_会議録.pdf",
            source_date="20260225",
            page=1,
            chunk_index=0,
            embedding=[0.0, 0.0],
        )
        chunk_analysis = RokunoheMinuteThemeChunkAnalysis(
            source_chunk=source_chunk,
            candidate_labels=["古いテーマ"],
            cluster_index=0,
        )
        cluster_analysis = RokunoheMinuteThemeClusterAnalysis(
            cluster_index=0,
            label="古いテーマ",
            representative_chunk_id="old_doc",
            chunks=[chunk_analysis],
        )
        repository.save_analysis_result(job=old_job, clusters=[cluster_analysis])

        deleted_count = repository.reset_analysis_results()

        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(RokunoheMinuteThemeAnalysisJob.objects.exists())


class RokunoheMinutesRagRepositoryTest(TestCase):
    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_uses_rokunohe_minutes_collection(self, mock_rag_service):
        """
        シナリオ:
        - 入力: APIキーのみを指定したRepository初期化。
        - 処理: Repositoryを生成する。
        - 期待値: 六戸町会議録専用collection名でRAGサービスが初期化されること。
        """
        RokunoheMinutesRagRepository(api_key="dummy")

        mock_rag_service.assert_called_once()
        self.assertEqual(
            mock_rag_service.call_args.kwargs["collection_name"],
            ROKUNOHE_MINUTES_COLLECTION_NAME,
        )

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_exists_checks_source_metadata(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB上に同じsource名の登録が存在するPDF。
        - 処理: Repositoryで存在確認を行う。
        - 期待値: sourceメタデータを条件に検索し、登録済みとしてTrueを返すこと。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {"ids": ["exists"]}
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        result = repository.exists(RokunoheMinutesPdf(path=Path("会議録.pdf")))

        self.assertTrue(result)
        rag_instance._collection.get.assert_called_once_with(
            where={"source": "会議録.pdf"},
            limit=1,
        )

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_delete_pdf_documents_removes_existing_source_documents(
        self, mock_rag_service
    ):
        """
        シナリオ:
        - 入力: Chroma DB上に同じsource名のドキュメントIDが存在するPDF。
        - 処理: RepositoryでPDF単位の削除を行う。
        - 期待値: source条件で取得したIDだけが削除されること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {"ids": ["doc_1", "doc_2"]}
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        repository.delete_pdf_documents(RokunoheMinutesPdf(path=Path("会議録.pdf")))

        rag_instance._collection.get.assert_called_once_with(
            where={"source": "会議録.pdf"}
        )
        rag_instance._collection.delete.assert_called_once_with(ids=["doc_1", "doc_2"])

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_reset_collection_removes_all_documents(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionにドキュメントIDが存在する状態。
        - 処理: Repositoryでcollectionリセットを行う。
        - 期待値: collection内の全IDが削除され、削除件数が返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {"ids": ["doc_1", "doc_2"]}
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        deleted_count = repository.reset_collection()

        rag_instance._collection.get.assert_called_once_with()
        rag_instance._collection.delete.assert_called_once_with(ids=["doc_1", "doc_2"])
        self.assertEqual(deleted_count, 2)

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_list_collection_items_returns_viewer_rows(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionがids、documents、metadatasを返す状態。
        - 処理: Repositoryで表示用一覧を取得する。
        - 期待値: Chroma ID、メタデータ、改行除去済み本文プレビューを持つ表示用データが返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {
            "ids": ["doc_1"],
            "documents": ["本文1行目\n本文2行目"],
            "metadatas": [
                {
                    "source": "20260225_会議録.pdf",
                    "source_date": "20260225",
                    "page": 1,
                    "chunk_index": 0,
                }
            ],
        }
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        items = repository.list_collection_items(limit=100)

        rag_instance._collection.get.assert_called_once_with(
            limit=100,
            offset=0,
            include=["documents", "metadatas"],
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].chroma_id, "doc_1")
        self.assertEqual(items[0].source, "20260225_会議録.pdf")
        self.assertEqual(items[0].source_date, "20260225")
        self.assertEqual(items[0].page, 1)
        self.assertEqual(items[0].chunk_index, 0)
        self.assertEqual(items[0].preview, "本文1行目 本文2行目")

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_count_collection_items_returns_chroma_count(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionが件数を返す状態。
        - 処理: Repositoryで登録件数を取得する。
        - 期待値: collection.count() の値が返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.count.return_value = 120
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        count = repository.count_collection_items()

        self.assertEqual(count, 120)
        rag_instance._collection.count.assert_called_once_with()

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_list_collection_items_filters_by_source_date_from(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionに直近1年内外のsource_dateを持つデータが存在する状態。
        - 処理: Repositoryで日付下限を指定して表示用一覧を取得する。
        - 期待値: source_dateが下限以降のデータだけ日付降順で返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {
            "ids": ["old_doc", "recent_old_doc", "recent_new_doc"],
            "documents": ["古い本文", "直近の古い本文", "直近の新しい本文"],
            "metadatas": [
                {"source": "20240101_会議録.pdf", "source_date": "20240101"},
                {"source": "20260225_会議録.pdf", "source_date": "20260225"},
                {"source": "20260301_会議録.pdf", "source_date": "20260301"},
            ],
        }
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        items = repository.list_collection_items(
            limit=100,
            offset=0,
            source_date_from=20250612,
        )

        rag_instance._collection.get.assert_called_once_with(
            include=["documents", "metadatas"],
        )
        self.assertEqual(
            [item.chroma_id for item in items], ["recent_new_doc", "recent_old_doc"]
        )

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_count_collection_items_filters_by_source_date_from(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionに直近1年内外のsource_date_ymdを持つデータが存在する状態。
        - 処理: Repositoryで日付下限を指定して件数を取得する。
        - 期待値: source_date_ymdが下限以降の件数が返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {
            "ids": ["old_doc", "recent_doc"],
            "documents": ["古い本文", "直近の本文"],
            "metadatas": [
                {"source": "20240101_会議録.pdf", "source_date_ymd": 20240101},
                {"source": "20260225_会議録.pdf", "source_date_ymd": 20260225},
            ],
        }
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        count = repository.count_collection_items(source_date_from=20250612)

        self.assertEqual(count, 1)

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_list_collection_items_returns_empty_when_collection_is_empty(
        self, mock_rag_service
    ):
        """
        シナリオ:
        - 入力: Chroma DB collectionにドキュメントIDが存在しない状態。
        - 処理: Repositoryで表示用一覧を取得する。
        - 期待値: 空リストが返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {"ids": []}
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        items = repository.list_collection_items(limit=100)

        self.assertEqual(items, [])

    @patch("llm_chat.domain.repository.completion.rokunohe_minutes.OpenAILlmRagService")
    def test_list_theme_source_chunks_returns_embeddings(self, mock_rag_service):
        """
        シナリオ:
        - 入力: Chroma DB collectionがids、documents、metadatas、embeddingsを返す状態。
        - 処理: Repositoryでテーマ分析用チャンク一覧を取得する。
        - 期待値: K-meansに使うembeddingと出典メタデータを持つVOが返ること。
        """
        rag_instance = mock_rag_service.return_value
        rag_instance._collection.get.return_value = {
            "ids": ["doc_1"],
            "documents": ["学校給食についての議論です。"],
            "metadatas": [
                {
                    "source": "20260225_会議録.pdf",
                    "source_date": "20260225",
                    "page": 1,
                    "chunk_index": 0,
                }
            ],
            "embeddings": [[0.1, 0.2, 0.3]],
        }
        repository = RokunoheMinutesRagRepository(api_key="dummy")

        chunks = repository.list_theme_source_chunks()

        rag_instance._collection.get.assert_called_once_with(
            include=["documents", "metadatas", "embeddings"],
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chroma_id, "doc_1")
        self.assertEqual(chunks[0].document, "学校給食についての議論です。")
        self.assertEqual(chunks[0].source, "20260225_会議録.pdf")
        self.assertEqual(chunks[0].embedding, [0.1, 0.2, 0.3])


class RokunohePdfDownloadCommandTest(TestCase):
    @patch(
        "llm_chat.management.commands.rokunohe_pdf_download.RokunoheMinutesPdfImportService"
    )
    def test_waits_between_external_requests(self, mock_import_service):
        """
        シナリオ:
        - 入力: PDFリンクを2件含むHTMLレスポンスと、リクエスト間隔0.1秒。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 2件目以降の外部リクエスト前に待機処理が呼び出されること。
        """
        mock_import_service.return_value.import_pdf.return_value = (
            RokunoheMinutesImportStatus.IMPORTED
        )

        first_page_response = self._create_response(
            '<a href="file1.pdf">会議録1 [PDF]</a><a href="file2.pdf">会議録2 [PDF]</a>'
        )
        pdf_response = self._create_response(
            "",
            content=b"%PDF",
            headers={"Last-Modified": "Wed, 25 Feb 2026 01:55:27 GMT"},
        )
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            with patch(
                "llm_chat.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[
                    first_page_response,
                    pdf_response,
                    pdf_response,
                    second_page_response,
                ],
            ), patch(
                "llm_chat.management.commands.rokunohe_pdf_download.time.sleep"
            ) as sleep_mock:
                stdout = StringIO()
                call_command(
                    "rokunohe_pdf_download",
                    save_dir=temp_dir,
                    delay=0.1,
                    stdout=stdout,
                )

        self.assertGreaterEqual(sleep_mock.call_count, 2)
        sleep_mock.assert_any_call(0.1)
        self.assertIn("進捗 1/2: ダウンロード中", stdout.getvalue())
        self.assertIn("進捗 2/2: ダウンロード中", stdout.getvalue())

    @patch(
        "llm_chat.management.commands.rokunohe_pdf_download.RokunoheMinutesPdfImportService"
    )
    def test_skips_existing_pdf_file(self, mock_import_service):
        """
        シナリオ:
        - 入力: 保存済みPDFと同じファイル名になるPDFリンクを含むHTMLレスポンス。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 保存済みPDFは再ダウンロードされず、HTML取得のみ実行されること。
        """
        mock_import_service.return_value.import_pdf.return_value = (
            RokunoheMinutesImportStatus.SKIPPED_EXISTING
        )

        first_page_response = self._create_response(
            '<a href="exists.pdf">保存済み [PDF]</a>'
        )
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            existing_pdf_path = Path(temp_dir) / "20260225_保存済み.pdf"
            existing_pdf_path.write_bytes(b"%PDF")

            with patch(
                "llm_chat.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[first_page_response, second_page_response],
            ) as get_mock:
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

        self.assertEqual(2, get_mock.call_count)

    @patch(
        "llm_chat.management.commands.rokunohe_pdf_download.RokunoheMinutesPdfImportService"
    )
    def test_prepends_last_modified_date_to_pdf_filename(self, mock_import_service):
        """
        シナリオ:
        - 入力: Last-Modifiedヘッダを持つPDFレスポンス。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: PDFがYYYYMMDD_ファイル名.pdf形式で保存されること。
        """
        mock_import_service.return_value.import_pdf.return_value = (
            RokunoheMinutesImportStatus.IMPORTED
        )

        first_page_response = self._create_response(
            '<a href="dated.pdf">会議録 [PDF]</a>'
        )
        pdf_response = self._create_response(
            "",
            content=b"%PDF",
            headers={"Last-Modified": "Wed, 25 Feb 2026 01:55:27 GMT"},
        )
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            with patch(
                "llm_chat.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[
                    first_page_response,
                    pdf_response,
                    second_page_response,
                ],
            ):
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

            self.assertTrue((Path(temp_dir) / "20260225_会議録.pdf").exists())

    def test_rejects_parallel_execution_with_lock_file(self):
        # ... (no change needed here as it fails before RAG service init)
        """
        シナリオ:
        - 入力: 保存先に実行中を示すロックファイルが存在する状態。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: CommandErrorが発生し、並行実行が拒否されること。
        """
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".rokunohe_pdf_download.lock"
            lock_path.write_text("running", encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

    @patch(
        "llm_chat.management.commands.rokunohe_pdf_download.RokunoheMinutesPdfImportService"
    )
    def test_imports_extracted_text_to_chroma(self, mock_import_service):
        """
        シナリオ:
        - 入力: PDFリンク1件と、PDF内のテキスト。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 保存されたPDFパスを使ってRAGインポートサービスが呼び出されること。
        """
        mock_import_service.return_value.import_pdf.return_value = (
            RokunoheMinutesImportStatus.IMPORTED
        )

        first_page_response = self._create_response(
            '<a href="test.pdf">会議録 [PDF]</a>'
        )
        pdf_response = self._create_response("", content=b"%PDF")
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            with patch(
                "llm_chat.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[first_page_response, pdf_response, second_page_response],
            ):
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

        mock_import_service.return_value.import_pdf.assert_called_once()
        args, _ = mock_import_service.return_value.import_pdf.call_args
        self.assertEqual(args[0].name, "会議録.pdf")

    @staticmethod
    def _create_response(
        text: str, content: bytes = b"", headers: dict[str, str] | None = None
    ) -> Mock:
        response = Mock()
        response.text = text
        response.content = content
        response.headers = headers or {}
        response.apparent_encoding = "utf-8"
        response.raise_for_status = Mock()
        return response
