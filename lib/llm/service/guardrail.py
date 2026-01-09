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


class OpenAIModerationGuardService(BaseGuardRailService):
    """
    OpenAI Moderation API を使用して、ユーザー入力とモデル出力の両面から安全性をチェックするガードレールサービス。

    本サービスの特徴:
    - 二重のガードレール: 「ユーザーが悪意のある入力を送っていないか」と「モデルが不適切な回答を生成していないか」の双方向を独立してチェックできます。
    - 最新モデルの利用: `omni-moderation-latest` を使用し、ヘイト、自傷行為、性的内容、暴力、ハラスメントなどの複数のカテゴリにわたる違反を詳細に検知します。
    - 柔軟なエラーハンドリング: APIエラーやタイムアウト時に、安全性を優先してブロックするか（厳格モード）、処理を続行させるかを設定可能です。

    注意点とトレードオフ:
    - パフォーマンスと遅延: 各チェック（入力・出力）において OpenAI の外部 API を呼び出すため、`SemanticGuardService` のようなローカル/ベクトル検索ベースの判定と比較して、ネットワーク遅延が発生します。特に「入出力の両面」でチェックを行う場合は、合計2回の追加 API コールが発生し、全体のレスポンス時間に影響する可能性があります。
    - 外部依存性: OpenAI API の稼働状況に依存します。

    処理の概要:
    1. テキスト（ユーザー入力またはモデル出力）を OpenAI Moderation API に送信します。
    2. API からのレスポンスに基づき、ポリシー違反（flagged）があるか判定します。
    3. 違反がある場合は、該当するカテゴリを特定し、サービス固有の拒否メッセージを伴う RED 信号を返します。
    4. 違反がない場合は、正常を示す GREEN 信号を返します。

    主な用途:
    - 入力チェック: プロンプトインジェクションの試みや、公序良俗に反するユーザー入力の遮断。
    - 出力チェック: AIモデルによる予期せぬ不適切な発言や、幻覚（ハルシネーション）に起因する有害情報の提供防止。
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
        OpenAI Moderation API を使用したテキストのモデレーションチェックの実装。

        処理の順番:
        1. OpenAI API を呼び出し、テキストのモデレーション判定を取得します。
        2. `flagged` が true の場合:
           - 違反カテゴリを抽出し、`blocked_message` と共に RED 信号を返します。
        3. 正常な場合（違反なし）:
           - GREEN 信号を返します。
        4. 例外（APIエラー等）発生時:
           - `strict_mode` が True の場合: 安全側に倒し、RED 信号を返します。
           - `strict_mode` が False の場合: 警告をログ出力し、チェックをスルー（GREEN）させます。

        Args:
            text: チェック対象のテキスト。
            entity_name: ログやエラーメッセージに表示するエンティティ名（例: "User", "Assistant"）。
            blocked_message: ブロック時にユーザーに表示する固定メッセージ。
            strict_mode: True の場合、APIエラー時もブロックします。デフォルトは False。

        Returns:
            SemanticGuardResult: 判定結果（GREEN または RED）。
        """
        try:
            response = self.openai_client.moderations.create(
                model="omni-moderation-latest", input=text
            )

            guardrail_result = response.results[0]
            if guardrail_result.flagged:
                flagged_categories = [
                    category
                    for category, flagged in guardrail_result.categories.model_dump().items()
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
        入力テキストのモデレーションチェック。
        テキストを OpenAI Moderation API (`omni-moderation-latest`) に送信します。

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
        出力テキストのモデレーションチェック。
        テキストを OpenAI Moderation API (`omni-moderation-latest`) に送信します。

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
    ベクトル検索（ChromaDB）を活用した、意味ベースのガードレールサービス。
    生成系LLMを通さずに、テキストの意味的な類似度（Embedding）に基づいて禁止ワードの検知やナレッジの適合性を判定します。

    本サービスの本質的な仕組み:
    - 「禁止ワード」をあらかじめベクトル空間上に配置しておき、入力テキストがそれらのベクトルと「近くない（距離が離れている）」ことをもって、安全（グリーン）であると判定します。
    - 単なる文字列の一致ではなく、意味の近接性を数値化（Distance）して評価するため、言い換えや類似表現も検知可能です。

    主な特徴とメリット:
    - 超高速・低遅延: 判定に生成系LLM（推論）を使用せず、Embeddingとベクトル検索のみで完結するため、LLMへのAPIリクエストに比べて圧倒的に高速に動作します。
    - 低コスト: トークン消費の激しい生成系LLMの呼び出し回数を削減して、ランニングコストを下げられます

    主な機能:
    1. 禁止ワード検知: 登録された禁止ワードリストと入力テキストの意味的な近さを判定。閾値より遠ければ安全とみなします。
    2. RAG適合性判定: 特定のナレッジ（RAGコレクション）に回答が含まれているかを確認します。

    アーキテクチャの概要:
    - 2つの ChromaDB コレクションを使い分けます。
        - `forbidden_words`: 意味的に不適切な単語やトピックを検知。
        - `portfolio_rag`: 回答可能な知識範囲を特定。
    - 生成系LLMのコストを抑えつつ、ベクトル空間上での幾何学的な位置関係に基づいた高度なフィルタリングを実現します。
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
        禁止ワードリストを Embedding 化して ChromaDB に登録します（初期化・更新用）。

        処理の流れ:
        1. 指定された名前のコレクションから、既存のデータをすべて削除します。
        2. 新しい禁止ワードのリストを受け取り、それぞれに対して Embedding を生成します。
        3. ID, Document, Metadata をセットにして ChromaDB に永続化します。
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
        ユーザーの入力がナレッジ（RAG）の範囲内にあるかを確認します。

        処理の詳細:
        - 入力テキストをベクトル化し、RAG用コレクションに対して類似検索を実行します。
        - 生成系LLMによる推論を行わないため、非常に高速に判定が可能です。
        - 1件でもドキュメントが見つかれば「ナレッジあり」と判定します。
        - 注意: 現時点では距離（Distance）による厳密なフィルタリングは行わず、存在確認のみを行います。
        """
        results = self._rag_collection.query(query_texts=[user_input], n_results=1)
        return bool(results and results.get("documents") and results["documents"][0])

    def check_forbidden_words(self, text: str):
        """
        テキストが禁止ワードに「意味的に」合致するかを判定します。

        判定ロジック（近接性によるフィルタリング）:
        1. あらかじめ用意された「禁止ワード」のベクトル群の中から、入力テキストに最も近いものを検索します。
           - この検索はローカル（またはベクトルDB）でのベクトル演算のみで行われるため、生成系LLMへのアクセスが発生せず、極めて低遅延です。
        2. 検索結果との距離（Distance）を測定します。
        3. 判定の根拠:
           - 距離が `threshold` (0.35) 以上であれば、禁止ワードと「近くない」ため、安全（グリーン）とみなします。
           - 距離が `threshold` (0.35) 未満の場合、意味的に極めて近いと判断し、ブロック（レッド）します。

        例外:
            SemanticGuardException: 禁止ワードとの距離が近く、リスクがあると判定された場合に発生します。
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
        意味差分検索パイプラインを実行し、入力の安全性を評価します。

        パイプラインのステップ:
        1. RAG確認: ユーザー入力がナレッジベースに存在するか確認します。
           - ヒットした場合: GREEN 判定で終了（信頼できる回答が可能なため）。
        2. RAGミス時: YELLOW 判定へ移行し、外部（一般LLM）への問い合わせを準備します。
        3. レスポンス生成: `llm_response_provider` を通じて一般LLMから回答を取得します。
        4. 出力検査: 一般LLMが生成した回答に対して、`check_forbidden_words` を実行します。
           - 禁止ワードが含まれる場合: RED 判定（例外発生）。
           - 含まれない場合: YELLOW 判定で回答を許可します。

        Args:
            user_input: ユーザーからの入力テキスト。
            llm_response_provider: (text) -> str の形式の呼び出し可能オブジェクト。RAGミス時の回答生成に使用。

        Returns:
            SemanticGuardResult: 最終的な判定結果（GREEN または YELLOW）。
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
        OpenAI Agents SDKで使用される入力・出力チェック用の関数を作成します。
        BaseGuardRailService のインターフェース実装です。

        ガードレールの性質:
        - 意味的な距離に基づくチェック: 入力・出力テキストが、あらかじめ登録された禁止ワードのベクトル群から「十分に離れている（近くない）」ことを検証します。
        - 距離が閾値を超えていれば（遠ければ）ブロックせず、閾値未満（近ければ）ブロックします。
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
