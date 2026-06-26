from unittest.mock import Mock, patch
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.service.completion.rag import OpenAIRagPdfImportService
from llm_chat.domain.use_case.completion.rag import OpenAIRagUseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rag import OpenAIRagPdfSource
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIRagPdfImportServiceTest(TestCase):
    def test_import_pdf_registers_documents_with_selected_pdf_metadata(self):
        """
        シナリオ:
        - 入力: 2ページ分の本文を抽出できるPDFと、モックRepository。
        - 処理: OpenAIRagPdfImportService.import_pdfを実行する。
        - 期待値: PDF IDを含むmetadataでVector DBへ登録され、登録日時が更新されること。
        """
        pdf_source = OpenAIRagPdfSource(
            pdf_id=10,
            display_name="サンプルPDF",
            path=Path("sample.pdf"),
            collection_name="openai_rag_pdf_10",
        )
        pdf_repository = Mock()
        pdf_repository.find_active.return_value = pdf_source
        vector_repository = Mock()

        page1 = Mock()
        page1.extract_text.return_value = "1ページ目の本文"
        page2 = Mock()
        page2.extract_text.return_value = "2ページ目の本文"
        reader = Mock()
        reader.pages = [page1, page2]

        with patch(
            "llm_chat.domain.service.completion.rag.PdfReader",
            return_value=reader,
        ):
            imported_count = OpenAIRagPdfImportService(
                pdf_repository=pdf_repository,
                vector_repository=vector_repository,
            ).import_pdf(10)

        self.assertEqual(imported_count, 2)
        vector_repository.delete_pdf_documents.assert_called_once_with(pdf_source)
        vector_repository.upsert_documents.assert_called_once()
        documents = vector_repository.upsert_documents.call_args.args[0]
        self.assertEqual(documents[0].page_content, "1ページ目の本文")
        self.assertEqual(documents[0].metadata["rag_pdf_id"], 10)
        self.assertEqual(documents[0].metadata["collection_name"], "openai_rag_pdf_10")
        self.assertEqual(
            documents[0].metadata["collection_label"].split("｜")[:3],
            ["PDF", "サンプルPDF", "text-embedding-3-small"],
        )
        self.assertEqual(
            documents[0].metadata["embedding_model"], "text-embedding-3-small"
        )
        self.assertEqual(documents[0].metadata["chunk_basis"], "page")
        self.assertEqual(documents[0].metadata["source"], "サンプルPDF")
        self.assertEqual(documents[0].metadata["file_name"], "サンプルPDF")
        self.assertEqual(documents[0].metadata["stored_file_name"], "sample.pdf")
        self.assertIn("imported_at", documents[0].metadata)
        pdf_repository.mark_imported.assert_called_once()
        self.assertEqual(pdf_repository.mark_imported.call_args.args[0], 10)
        self.assertIn("imported_at", pdf_repository.mark_imported.call_args.kwargs)


class OpenAIRagUseCaseTest(TestCase):
    def test_execute_requires_selected_pdf(self):
        """
        シナリオ:
        - 入力: PDF ID未指定のOpenAI RAG質問。
        - 処理: OpenAIRagUseCase.executeを実行する。
        - 期待値: PDF選択を促すValueErrorが発生すること。
        """
        user = User.objects.create_user(username="rag-user")

        with self.assertRaisesMessage(
            ValueError, "RAGに使用するPDFを選択してください。"
        ):
            OpenAIRagUseCase().execute(user=user, content="質問", rag_pdf_id="")

    def test_execute_passes_selected_pdf_to_service(self):
        """
        シナリオ:
        - 入力: PDF ID付きのOpenAI RAG質問と、モック化したRAG Service。
        - 処理: OpenAIRagUseCase.executeを実行する。
        - 期待値: 選択PDF IDがServiceへ渡され、assistant履歴がOpenAI RAGとして保存されること。
        """
        user = User.objects.create_user(username="rag-user")
        assistant_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content="回答",
            model_name="gpt-5-mini",
            use_case_type=UseCaseType.OPENAI_RAG,
        )

        with patch(
            "llm_chat.domain.use_case.completion.rag.OpenAIRagPdfRepository.exists_active",
            return_value=True,
        ), patch(
            "llm_chat.domain.use_case.completion.rag.OpenAIRagService"
        ) as service_mock:
            service_mock.return_value.model_name = "gpt-5-mini"
            service_mock.return_value.generate.return_value = assistant_message

            result = OpenAIRagUseCase().execute(
                user=user,
                content="質問",
                rag_pdf_id="12",
            )

        service_mock.return_value.generate.assert_called_once()
        self.assertEqual(
            service_mock.return_value.generate.call_args.kwargs["pdf_id"], 12
        )
        self.assertEqual(result.content, "回答")
        self.assertEqual(result.use_case_type, UseCaseType.OPENAI_RAG)
