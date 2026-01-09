from abc import ABC, abstractmethod
import os
import logging
from pathlib import Path
from typing import Callable

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from openai import OpenAI

from lib.llm.valueobject.guardrail import (
    GuardRailSignal,
    SemanticGuardResult,
    SemanticGuardException,
)
from config.settings import BASE_DIR

logger = logging.getLogger(__name__)


class BaseGuardRailService(ABC):
    """
    ガードレールサービスの基底クラス
    """

    @abstractmethod
    def create_guardrail(self, *args, **kwargs) -> Callable:
        """
        OpenAI Agents SDKで使用されるガードレール関数を作成する
        """
        pass


class OpenAIModerationService(BaseGuardRailService):
    """
    Moderation機能を提供するサービス
    OpenAI Moderation APIを使用した入力・出力のチェック機能
    """

    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _check_moderation(
        self,
        text: str,
        entity_name: str,
        blocked_message: str,
        strict_mode: bool = False,
    ) -> SemanticGuardResult:
        """
        OpenAI Moderation APIを使用したテキストのモデレーションチェック

        Args:
            text: チェック対象のテキスト
            entity_name: エンティティ名
            blocked_message: ブロック時のメッセージ
            strict_mode: 厳格モードかどうか

        Returns:
            SemanticGuardResult
        """
        try:
            response = self.openai_client.moderations.create(
                model="omni-moderation-latest", input=text
            )

            moderation_result = response.results[0]
            if moderation_result.flagged:
                flagged_categories = [
                    category
                    for category, flagged in moderation_result.categories.model_dump().items()
                    if flagged
                ]
                return SemanticGuardResult(
                    signal=GuardRailSignal.RED,
                    reason="MODERATION_FLAGGED",
                    detail=f"{entity_name}: {blocked_message} (カテゴリ: {', '.join(flagged_categories)})",
                )

            return SemanticGuardResult(signal=GuardRailSignal.GREEN)
        except Exception as e:
            logger.warning(f"OpenAI Moderation API error: {e}")
            if strict_mode:
                return SemanticGuardResult(
                    signal=GuardRailSignal.RED,
                    reason="MODERATION_ERROR",
                    detail=f"{entity_name}: 現在、安全性チェックが利用できません。しばらくしてから再度お試しください。",
                )
            return SemanticGuardResult(signal=GuardRailSignal.GREEN)

    def check_input_moderation(
        self, input_text: str, entity_name: str, strict_mode: bool = False
    ) -> SemanticGuardResult:
        """
        入力テキストのモデレーションチェック

        Args:
            input_text: チェック対象の入力テキスト
            entity_name: エンティティ名
            strict_mode: 厳格モードかどうか

        Returns:
            SemanticGuardResult
        """
        return self._check_moderation(
            input_text,
            entity_name,
            "申し訳ありませんが、その内容は適切ではないため、お答えできません。",
            strict_mode,
        )

    def check_output_moderation(
        self, output_text: str, entity_name: str
    ) -> SemanticGuardResult:
        """
        出力テキストのモデレーションチェック

        Args:
            output_text: チェック対象の出力テキスト
            entity_name: エンティティ名

        Returns:
            SemanticGuardResult
        """
        return self._check_moderation(
            output_text,
            entity_name,
            "申し訳ありませんが、適切な回答を生成できませんでした。別の質問をお試しください。",
        )

    @staticmethod
    def _convert_semantic_result_to_dict(
        result: SemanticGuardResult,
    ) -> dict[str, bool | str]:
        """
        SemanticGuardResultをOpenAI Agents SDKが期待する形式に変換

        Args:
            result: セマンティックガード結果

        Returns:
            変換された辞書
        """
        blocked = result.signal == GuardRailSignal.RED
        return {"blocked": blocked, "message": result.detail or ""}

    def create_guardrail(self, entity_name: str, strict_mode: bool = False) -> Callable:
        """
        OpenAI Moderation APIを使用した入力ガードレール関数を作成
        BaseGuardRailService のインターフェース実装

        Args:
            entity_name: エンティティ名
            strict_mode: 厳格モードかどうか

        Returns:
            ガードレール関数 (context, agent, input_text) -> dict[str, bool | str]
        """

        def moderation_check(_, __, input_text: str) -> dict[str, bool | str]:
            result = self.check_input_moderation(input_text, entity_name, strict_mode)
            return self._convert_semantic_result_to_dict(result)

        return moderation_check

    def create_output_moderation_guardrail(self, entity_name: str) -> Callable:
        """
        出力用モデレーションガードレール関数を作成

        Args:
            entity_name: エンティティ名

        Returns:
            出力ガードレール関数 (context, agent, output_text) -> dict[str, bool | str]
            OpenAI Agents SDKで使用される出力チェック用の関数
        """

        def output_moderation_check(_, __, output_text: str) -> dict[str, bool | str]:
            result = self.check_output_moderation(output_text, entity_name)
            return self._convert_semantic_result_to_dict(result)

        return output_moderation_check


class SemanticGuardService(BaseGuardRailService):
    """
    Chroma を用いた意味差分検索ガードレール
    生成系LLMを呼ばず、embedding + ベクトル検索のみで禁止ワード等を検知する
    """

    def __init__(
        self,
        api_key: str | None = None,
        persist_directory: str | None = None,
        forbidden_words_collection_name: str = "forbidden_words",
        rag_collection_name: str = "portfolio_rag",
        embedding_model: str = "text-embedding-3-small",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for SemanticGuardService")

        self.embedding_model = embedding_model

        persist_path = persist_directory or os.getenv("CHROMA_DB_PATH", "./chroma_db")
        if not os.path.isabs(persist_path):
            persist_path = str(Path(BASE_DIR) / persist_path)

        self._client_db = chromadb.PersistentClient(
            path=persist_path, settings=Settings(allow_reset=True)
        )
        self.openai_ef = OpenAIEmbeddingFunction(
            api_key=self.api_key, model_name=self.embedding_model
        )

        # 禁止ワード用コレクション
        self._forbidden_words_collection = self._client_db.get_or_create_collection(
            name=forbidden_words_collection_name, embedding_function=self.openai_ef
        )

        # ナレッジ検索用コレクション（既存のコレクションを参照することを想定）
        self._rag_collection = self._client_db.get_or_create_collection(
            name=rag_collection_name, embedding_function=self.openai_ef
        )

    def setup_forbidden_words(self, words: list[str]):
        """
        禁止ワードリストを embedding 化して Chroma に永続化する（初期化フェーズ用）
        既存の禁止ワードはすべて削除され、新しいリストで上書きされます。
        """
        logger.info(f"Setting up {len(words)} forbidden words...")

        # 1. 既存の禁止ワードを取得して削除
        existing_data = self._forbidden_words_collection.get()
        if existing_data["ids"]:
            self._forbidden_words_collection.delete(ids=existing_data["ids"])
            logger.debug(
                f"Cleared {len(existing_data['ids'])} existing forbidden words."
            )

        # 2. 新しいワードを登録
        ids = [f"word_{i}" for i in range(len(words))]
        metadatas = [{"word": word} for word in words]

        self._forbidden_words_collection.upsert(
            ids=ids, documents=words, metadatas=metadatas
        )
        logger.info("Forbidden words setup completed.")

    def check_rag_hit(self, user_input: str) -> bool:
        """
        RAGにヒットするか確認する
        documents が空でなければヒットとみなす（距離の閾値は要検討だが、まずは存在確認）
        """
        results = self._rag_collection.query(query_texts=[user_input], n_results=1)
        return bool(results and results.get("documents") and results["documents"][0])

    def check_forbidden_words(self, text: str):
        """
        禁止ワードに意味的にヒットするか確認する
        ヒットした場合は SemanticGuardException を投げる

        ※このメソッドは embedding API を呼び出しますが、生成系LLMは呼び出しません。
        """
        # 距離(distance)の閾値を設定。意味的に近いものを検知するため
        # OpenAI embedding の場合、0.2~0.4 程度が「かなり近い」
        threshold = 0.35

        results = self._forbidden_words_collection.query(
            query_texts=[text], n_results=1
        )

        if results and results.get("distances") and results["distances"][0]:
            distance = results["distances"][0][0]
            word = results["documents"][0][0]

            logger.debug(f"Forbidden word search: distance={distance}, word={word}")

            if distance < threshold:
                logger.warning(
                    f"🔴 RED: Forbidden word detected: {word} (distance: {distance})"
                )
                raise SemanticGuardException(
                    SemanticGuardResult(
                        signal=GuardRailSignal.RED,
                        reason="FORBIDDEN_WORD_DETECTED",
                        detail=f"禁止ワード「{word}」に意味的にヒットしました。",
                    )
                )

    def evaluate(
        self, user_input: str, llm_response_provider=None
    ) -> SemanticGuardResult:
        """
        意味差分検索パイプラインを実行する

        1. ナレッジ検索（RAGヒット確認）
        2. RAGヒットあり -> GREEN
        3. RAGヒットなし -> YELLOW -> 一般LLM問い合わせ
        4. 一般LLM出力の禁止ワード除外検査
        5. ヒットすれば RED (Exception)
        """
        logger.info(f"Evaluating user input: {user_input[:50]}...")

        # 1. RAGヒット確認
        if self.check_rag_hit(user_input):
            logger.info("🟢 GREEN: RAG hit.")
            return SemanticGuardResult(
                signal=GuardRailSignal.GREEN,
                reason="RAG_HIT",
                detail="社内ナレッジに基づく回答が可能です。",
            )

        # 2. RAGヒットなし
        logger.info("🟡 YELLOW: RAG miss. Proceeding to general LLM.")
        if llm_response_provider is None:
            return SemanticGuardResult(
                signal=GuardRailSignal.YELLOW,
                reason="RAG_MISS",
                detail="RAGヒットなし。一般LLM問い合わせが必要です（レスポンスプロバイダ未指定）。",
            )

        # 3. 一般LLM問い合わせ
        llm_response = llm_response_provider(user_input)

        # 4. 禁止ワード除外検査 (RED判定ならException)
        self.check_forbidden_words(llm_response)

        return SemanticGuardResult(
            signal=GuardRailSignal.YELLOW,
            reason="RAG_MISS",
            detail="一般LLM問い合わせルート（禁止ワードチェック通過）",
        )

    def create_guardrail(self, *args, **kwargs) -> Callable:
        """
        OpenAI Agents SDKで使用される入力・出力チェック用の関数を作成
        BaseGuardRailService のインターフェース実装
        """

        def semantic_check(_, __, text: str) -> dict[str, bool | str]:
            try:
                self.check_forbidden_words(text)
                return {"blocked": False}
            except SemanticGuardException as sge:
                return {"blocked": True, "message": sge.result.detail}
            except Exception as e:
                logger.warning(f"Semantic Guard error: {e}")
                return {"blocked": False}

        return semantic_check
