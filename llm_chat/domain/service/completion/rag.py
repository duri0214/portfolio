import os
from zoneinfo import ZoneInfo

from django.utils import timezone
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from pypdf import PdfReader

from llm_chat.domain.repository.completion.rag import (
    OpenAIRagPdfRepository,
    OpenAIRagVectorRepository,
)
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rag import (
    OpenAIRagDocument,
    OpenAIRagPdfMetadata,
    OpenAIRagPdfSource,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIRagPdfImportService:
    """
    アップロード済みPDFをOpenAI RAG用Vector DBへ登録するService。

    PDF管理画面で保存された1つのPDFをページ単位で読み取り、同じPDF ID由来の
    既存チャンクを削除してからChroma DBへ登録します。
    """

    def __init__(
        self,
        *,
        pdf_repository: OpenAIRagPdfRepository | None = None,
        vector_repository: OpenAIRagVectorRepository | None = None,
    ) -> None:
        self.pdf_repository = pdf_repository or OpenAIRagPdfRepository()
        self.vector_repository = vector_repository

    def import_pdf(self, pdf_id: int, pdf_file=None) -> int:
        """
        PDFをVector DBへ登録し、登録したページ数を返します。

        Args:
            pdf_id: 登録対象のOpenAIRagPdf ID。
            pdf_file: アップロードされたPDFファイル。指定時はサーバーへ保存せず直接読み込みます。

        Returns:
            int: Vector DBへ登録したドキュメント件数。

        Side Effects:
            同じPDF ID由来の既存Chromaチャンクを削除し、PDF本文を再登録します。
        """
        pdf = self.pdf_repository.find_active(pdf_id)
        imported_at = timezone.now()
        documents = self._create_documents(
            pdf,
            imported_at=imported_at.astimezone(ZoneInfo("Asia/Tokyo"))
            .replace(microsecond=0)
            .strftime("%Y-%m-%d %H:%M:%S"),
            pdf_file=pdf_file,
        )
        if not documents:
            return 0

        vector_repository = self._get_vector_repository(pdf)
        vector_repository.delete_pdf_documents(pdf)
        vector_repository.upsert_documents(documents)
        self.pdf_repository.mark_imported(pdf.pdf_id, imported_at=imported_at)
        return len(documents)

    def _get_vector_repository(
        self, pdf: OpenAIRagPdfSource
    ) -> OpenAIRagVectorRepository:
        if self.vector_repository is not None:
            return self.vector_repository

        return OpenAIRagVectorRepository(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            collection_name=pdf.collection_name,
        )

    @staticmethod
    def _create_documents(
        pdf: OpenAIRagPdfSource, *, imported_at: str, pdf_file=None
    ) -> list[OpenAIRagDocument]:
        if pdf_file and hasattr(pdf_file, "seek"):
            pdf_file.seek(0)
        reader = PdfReader(pdf_file or pdf.path)
        documents = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            metadata = OpenAIRagPdfMetadata(
                pdf=pdf,
                page=page_index,
                chunk_index=page_index - 1,
                imported_at=imported_at,
            )
            documents.append(
                OpenAIRagDocument(
                    page_content=text.strip(),
                    metadata=metadata.to_dict(),
                )
            )
        return documents


class OpenAIRagService(BaseChatService):
    """
    ユーザーが選択した登録済みPDFを対象にRAG回答を生成するService。

    固定サンプルPDFは暗黙には読み込まず、チャット画面から渡されたPDF IDで
    OpenAI RAG用collectionの検索対象を絞ります。

    Attributes:
        model_name: OpenAI RAG回答生成に使用するLLMモデル名。
    """

    model_name = ModelName.GPT_5_MINI

    def __init__(self, repository: OpenAIRagVectorRepository | None = None):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )
        self.repository = repository

    def generate(self, user_message: MessageDTO, *, pdf_id: int) -> MessageDTO:
        """
        ユーザー質問に対して、選択されたPDFだけを根拠にRAG回答を生成します。

        Args:
            user_message: ユーザーの質問内容を持つMessageDTO。
            pdf_id: チャット画面で選択されたOpenAIRagPdf ID。

        Returns:
            MessageDTO: RAG回答本文をcontentに持つassistantメッセージ。
        """
        if self.repository is not None:
            repository = self.repository
        else:
            pdf = OpenAIRagPdfRepository.find_active(pdf_id)
            repository = OpenAIRagVectorRepository(
                api_key=self.config.api_key,
                model=self.config.model,
                collection_name=pdf.collection_name,
            )
        response = repository.retrieve_answer(
            user_message.to_message(),
            pdf_id=pdf_id,
        )

        return self._create_assistant_message(
            user=user_message.user,
            content=response.answer,
            use_case_type=UseCaseType.OPENAI_RAG,
        )
