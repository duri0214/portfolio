import os
from pathlib import Path

from pypdf import PdfReader

from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.repository.completion.rokunohe_minutes import (
    RokunoheMinutesRagRepository,
)
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    RokunoheMinutesDocument,
    RokunoheMinutesImportStatus,
    RokunoheMinutesMetadata,
    RokunoheMinutesPdf,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RokunoheMinutesPdfImportService:
    """
    六戸町会議録PDFの本文抽出とRAG登録手順を担当するService。
    """

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None) -> None:
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )

    def import_pdf(self, pdf_path: Path) -> RokunoheMinutesImportStatus:
        pdf = RokunoheMinutesPdf(path=pdf_path)
        if self.repository.exists(pdf):
            return RokunoheMinutesImportStatus.SKIPPED_EXISTING

        document = self._create_document(pdf)
        if document is None:
            return RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT

        self.repository.upsert_documents([document])
        return RokunoheMinutesImportStatus.IMPORTED

    @staticmethod
    def _create_document(pdf: RokunoheMinutesPdf) -> RokunoheMinutesDocument | None:
        reader = PdfReader(pdf.path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        full_text = "\n".join(text_parts).strip()
        if not full_text:
            return None

        metadata = RokunoheMinutesMetadata.from_pdf(pdf)
        return RokunoheMinutesDocument(
            page_content=full_text,
            metadata=metadata.to_dict(),
        )


class RokunoheMinutesRagService(BaseChatService):
    model_name = ModelName.GPT_5_MINI

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=self.config.api_key,
            model=self.config.model,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        # 既にインデックス済みであることを前提とする
        response = self.repository.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response.answer,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
