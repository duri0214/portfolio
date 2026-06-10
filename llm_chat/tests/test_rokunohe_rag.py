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
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RokunoheRagViewTest(TestCase):
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
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
        - 期待値: 管理コマンドが呼び出され、六戸町会議録QAページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch("llm_chat.views.call_command") as call_command_mock:
            response = self.client.post(reverse("llm:rokunohe_pdf_download"))

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )
        call_command_mock.assert_called_once_with("rokunohe_pdf_download")

    def test_non_superuser_cannot_start_pdf_download(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
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
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
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
        ):
            response = self.client.post(reverse("llm:rokunohe_pdf_download"))

        self.assertRedirects(
            response,
            reverse("llm:rokunohe_minutes"),
            fetch_redirect_response=False,
        )

    def test_superuser_sees_pdf_download_button(self):
        """
        シナリオ:
        - 入力: superuserでログインした状態。
        - 処理: 六戸町会議録QAページを表示する。
        - 期待値: 会議録PDF保存ボタンが表示されること。
        """
        user = User.objects.create_superuser(
            username="admin3",
            email="admin3@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("llm:rokunohe_minutes"))

        self.assertContains(response, "会議録PDF保存")

    def test_non_superuser_does_not_see_pdf_download_button(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: 六戸町会議録QAページを表示する。
        - 期待値: 会議録PDF保存ボタンが表示されないこと。
        """
        user = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("llm:rokunohe_minutes"))

        self.assertNotContains(response, "会議録PDF保存")


class RokunohePdfDownloadCommandTest(TestCase):
    @patch("llm_chat.management.commands.rokunohe_pdf_download.OpenAILlmRagService")
    @patch("llm_chat.management.commands.rokunohe_pdf_download.PdfReader")
    def test_waits_between_external_requests(self, mock_pdf, mock_rag):
        """
        シナリオ:
        - 入力: PDFリンクを2件含むHTMLレスポンスと、リクエスト間隔0.1秒。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 2件目以降の外部リクエスト前に待機処理が呼び出されること。
        """
        # モックの設定
        mock_pdf_instance = mock_pdf.return_value
        mock_page = Mock()
        mock_page.extract_text.return_value = "テストテキスト"
        mock_pdf_instance.pages = [mock_page]

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

    @patch("llm_chat.management.commands.rokunohe_pdf_download.OpenAILlmRagService")
    @patch("llm_chat.management.commands.rokunohe_pdf_download.PdfReader")
    def test_skips_existing_pdf_file(self, mock_pdf, mock_rag):
        """
        シナリオ:
        - 入力: 保存済みPDFと同じファイル名になるPDFリンクを含むHTMLレスポンス。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 保存済みPDFは再ダウンロードされず、HTML取得のみ実行されること。
        """
        # インポート済みと判定されるように設定
        mock_rag.return_value._collection.get.return_value = {"ids": ["exists"]}

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

    @patch("llm_chat.management.commands.rokunohe_pdf_download.OpenAILlmRagService")
    @patch("llm_chat.management.commands.rokunohe_pdf_download.PdfReader")
    def test_prepends_last_modified_date_to_pdf_filename(self, mock_pdf, mock_rag):
        """
        シナリオ:
        - 入力: Last-Modifiedヘッダを持つPDFレスポンス。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: PDFがYYYYMMDD_ファイル名.pdf形式で保存されること。
        """
        # モックの設定
        mock_pdf_instance = mock_pdf.return_value
        mock_page = Mock()
        mock_page.extract_text.return_value = "テストテキスト"
        mock_pdf_instance.pages = [mock_page]

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

    @patch("llm_chat.management.commands.rokunohe_pdf_download.OpenAILlmRagService")
    @patch("llm_chat.management.commands.rokunohe_pdf_download.PdfReader")
    def test_imports_extracted_text_to_chroma(self, mock_pdf, mock_rag):
        """
        シナリオ:
        - 入力: PDFリンク1件と、PDF内のテキスト。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: PDFからテキストが抽出され、RAGサービスのupsert_documentsが呼び出されること。
        """
        pdf_text = "六戸町会議録の内容です。"
        mock_pdf_instance = mock_pdf.return_value
        mock_page = Mock()
        mock_page.extract_text.return_value = pdf_text
        mock_pdf_instance.pages = [mock_page]

        rag_instance = mock_rag.return_value
        rag_instance._collection.get.return_value = {"ids": []}  # 未登録

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

        rag_instance.upsert_documents.assert_called_once()
        args, _ = rag_instance.upsert_documents.call_args
        docs = args[0]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, pdf_text)
        self.assertEqual(docs[0].metadata["source"], "会議録.pdf")

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
