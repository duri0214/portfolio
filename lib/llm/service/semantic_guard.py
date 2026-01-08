import os
import logging
from pathlib import Path
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from collections.abc import Callable
from lib.llm.valueobject.semantic_guard import (
    GuardRailSignal,
    SemanticGuardResult,
    SemanticGuardException,
)

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)


class SemanticGuardService:
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

        # RAG用コレクション（既存のものを参照）
        self._rag_collection = self._client_db.get_or_create_collection(
            name=rag_collection_name, embedding_function=self.openai_ef
        )

    def setup_forbidden_words(self, words: list[str]):
        """
        禁止ワードリストを embedding 化して Chroma に永続化する（初期化フェーズ用）
        """
        logger.info(f"Setting up {len(words)} forbidden words...")
        ids = [f"word_{i}" for i in range(len(words))]
        metadatas = [{"word": word} for word in words]

        # 一旦全削除してから追加（簡易更新）
        # self._forbidden_words_collection.delete(ids=ids) # 既存IDが不明な場合があるので全削除が望ましいが
        # ここでは単純にupsert
        self._forbidden_words_collection.upsert(
            ids=ids, documents=words, metadatas=metadatas
        )
        logger.info("Forbidden words setup completed.")

    def check_rag_hit(self, user_input: str) -> bool:
        """
        RAGにヒットするか確認する
        """
        results = self._rag_collection.query(query_texts=[user_input], n_results=1)
        # documents が空でなければヒットとみなす（距離の閾値は要検討だが、まずは存在確認）
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

        1. RAG検索
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


class SemanticGuardServiceWrapper:
    """
    SemanticGuardServiceをOpenAI Agents SDKのガードレール形式に適合させるためのラッパー
    """

    def __init__(self, service: SemanticGuardService):
        self.service = service

    def create_guardrail(self) -> Callable:
        """
        OpenAI Agents SDKで使用される入力・出力チェック用の関数を作成
        注: この実装では入力段階でRAGヒットを確認し、ヒットしない場合はYELLOWとして
        LLM実行後に禁止ワードチェックを行うフローを想定している。
        """

        def semantic_check(_, __, text: str) -> dict[str, bool | str]:
            try:
                # 簡易的に、テキストが渡された際に禁止ワードチェックのみを行う単体ガードレールとしても機能させる
                self.service.check_forbidden_words(text)
                return {"blocked": False}
            except SemanticGuardException as wrapper_sge:
                return {"blocked": True, "message": wrapper_sge.result.detail}
            except Exception as wrapper_ex:
                logger.warning(f"Semantic Guard error: {wrapper_ex}")
                return {"blocked": False}

        return semantic_check


if __name__ == "__main__":
    # セットアップ / 簡易テスト用エントリーポイント

    mode = os.getenv("MODE", "run")
    guard = SemanticGuardService()

    if mode == "setup":
        forbidden_words = [
            "佐川急便",
            "Amazon Logistics",
            "日本郵便",
        ]
        guard.setup_forbidden_words(forbidden_words)
    elif mode == "run":
        # 簡易テスト
        test_input = "荷物の配送状況を教えてください"
        try:
            # 擬似LLMプロバイダ
            def mock_llm_response(_):
                return "佐川急便で配送中です。"  # REDを誘発

            result = guard.evaluate(test_input, mock_llm_response)
            print(f"Result: {result}")
        except SemanticGuardException as sge:
            print(f"GuardRail Triggered: {sge.result}")
        except Exception as ex:
            print(f"Error: {ex}")
