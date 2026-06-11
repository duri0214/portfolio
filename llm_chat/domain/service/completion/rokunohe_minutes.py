import os
from pathlib import Path

from django.contrib.auth.models import User
from lib.llm.valueobject.completion import RoleType
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

    このServiceは単一PDFファイルを対象に、登録済み確認、PDF本文抽出、
    RAG登録用ドキュメント生成、Repository経由のChroma DB登録までの手順を制御します。
    Chroma DBの具体的な永続化操作はRepositoryへ委譲し、PDF読み取りと登録フローの判断だけを扱います。
    """

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None) -> None:
        """
        六戸町会議録PDFインポートServiceを初期化します。

        Args:
            repository: Chroma DBへの登録済み確認とドキュメント登録を担当するRepository。
                テスト時はモックRepositoryを渡し、本番時は未指定のまま環境変数のAPIキーを使って生成します。
        """
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )

    def import_pdf(self, pdf_path: Path) -> RokunoheMinutesImportStatus:
        """
        単一PDFを六戸町会議録RAGへ登録します。

        Args:
            pdf_path: ローカルに保存済みの六戸町会議録PDFファイルパス。

        Returns:
            RokunoheMinutesImportStatus:
                - IMPORTED: PDF本文を抽出し、Chroma DBへ登録した。
                - SKIPPED_EXISTING: 同じsource名のPDFが登録済みだった。
                - SKIPPED_EMPTY_TEXT: PDFから登録可能な本文を抽出できなかった。

        Side Effects:
            未登録かつ本文抽出に成功した場合、Repository経由でChroma DBへドキュメントを登録します。
        """
        pdf = RokunoheMinutesPdf(path=pdf_path)
        if self.repository.exists(pdf):
            return RokunoheMinutesImportStatus.SKIPPED_EXISTING

        documents = self._create_documents(pdf)
        if not documents:
            return RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT

        self.repository.upsert_documents(documents)
        return RokunoheMinutesImportStatus.IMPORTED

    @staticmethod
    def _create_documents(pdf: RokunoheMinutesPdf) -> list[RokunoheMinutesDocument]:
        """
        PDF本文とメタデータからRAG登録用ドキュメントを作成します。

        Args:
            pdf: 本文抽出対象の六戸町会議録PDF。

        Returns:
            list[RokunoheMinutesDocument]:
                ページ単位の抽出本文とsource/page/dateメタデータを持つドキュメント。
                PDFから空文字しか得られない場合は空リストを返します。

        Side Effects:
            PDFファイルを読み取り、各ページからテキストを抽出します。
        """
        reader = PdfReader(pdf.path)
        documents = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            metadata = RokunoheMinutesMetadata.from_pdf(
                pdf,
                page=page_index,
                chunk_index=page_index - 1,
            )
            documents.append(
                RokunoheMinutesDocument(
                    page_content=text.strip(),
                    metadata=metadata.to_dict(),
                )
            )

        return documents


class RokunoheMinutesRagService(BaseChatService):
    """
    六戸町会議録RAGの質問応答メッセージ生成を担当するService。

    このServiceは、既にChroma DBへ登録済みの `rokunohe_minutes` collection を前提に、
    ユーザー質問をRepositoryへ渡してRAG回答を取得し、チャット表示用のMessageDTOへ変換します。

    Attributes:
        model_name: 六戸町会議録RAG回答生成に使用するLLMモデル名。
    """

    model_name = ModelName.GPT_5_MINI
    initial_summary_prompt = (
        "取り込み済みの六戸町会議録を横断して、分析の入口になる初回サマリーを作成してください。"
        "主要テーマ、直近の傾向、深掘りに向く質問例を日本語で簡潔に箇条書きしてください。"
        "根拠にした会議録の出典も分かる範囲で添えてください。"
    )

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None):
        """
        六戸町会議録RAG回答生成Serviceを初期化します。

        Args:
            repository: RAG検索と回答生成を担当するRepository。
                テスト時はモックRepositoryを渡し、本番時は未指定のままOpenAI設定から生成します。
        """
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
        """
        ユーザー質問に対する六戸町会議録RAG回答を生成します。

        Args:
            user_message: ユーザーの質問内容を持つMessageDTO。

        Returns:
            MessageDTO:
                Repositoryが返したRAG回答本文をcontentに持つassistantメッセージ。

        Side Effects:
            Repository経由でChroma DB検索とLLM回答生成を行います。
            このメソッド自体はChatLogsへの保存を行わず、保存はUseCase層が担当します。
        """
        response = self.repository.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response.answer,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )

    def generate_initial_summary(self, user: User) -> MessageDTO:
        """
        PDF取り込み直後に表示する分析入口用サマリーを生成します。

        Args:
            user: サマリーを保存する対象ユーザー。

        Returns:
            MessageDTO: チャット履歴へ保存するassistantメッセージ。
        """
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=self.initial_summary_prompt,
            model_name=self.model_name,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        return self.generate(user_message)
