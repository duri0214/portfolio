import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generator, Iterable, Sequence

from dotenv import load_dotenv
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import ChatCompletion
from openai.types.responses import EasyInputMessageParam

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.completion import Message, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig

# .env ファイルを読み込む
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def cut_down_chat_history(
    chat_history: list[Message],
    max_messages: int = 5,
) -> list[Message]:
    """
    チャット履歴メッセージのリストを削減し、直近のメッセージ件数を max_messages に制限します。

    以前はトークン数ベースで履歴を管理していましたが、メッセージ件数ベースに変更しました：
    本来はtiktoken等を利用してトークンを算出し、モデルごとのllm-max-inputのようなトークン制限値に基づいてダイエットするべきですが、
    LLMに入力するために絞る方法として単純に最新5件のメッセージに簡略化したため、
    現在はトークン数による削減は行わず、単純にメッセージ件数ベースで直近のメッセージのみを保持するようになっています。

    Args:
        chat_history (list[Message]): チャット履歴メッセージのリスト。
        max_messages (int, optional): 保持する最大メッセージ件数。デフォルト値は5。

    Returns:
        list[Message]: 直近のmax_messages件に削減されたチャット履歴メッセージのリスト。
    """
    if not chat_history:
        return []

    if len(chat_history) <= max_messages:
        return chat_history
    else:
        return chat_history[-max_messages:]


class LlmService(ABC):
    """
    LLMサービスの基底クラス。すべてのLLMサービス実装はこのクラスを継承します。
    """

    @abstractmethod
    def retrieve_answer(self, **kwargs):
        """
        LLMから回答を取得するための抽象メソッド。
        各サブクラスで具体的な実装を提供する必要があります。

        Args:
            **kwargs: サービス固有のパラメータ

        Returns:
            LLMからの応答
        """
        pass


class LlmCompletionService(LlmService):
    """
    OpenAIとGeminiの両方に対応した統合LLM完了サービス。
    OpenAIのAPIインターフェースを使用してGeminiモデルにもアクセスできます。

    See Also: https://ai.google.dev/gemini-api/docs/openai
    """

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config
        self.client = self._initialize_client()

    def _initialize_client(self) -> OpenAI:
        """
        APIクライアントを初期化します。
        GeminiConfigの場合はOpenAI互換エンドポイントを使用します。

        Returns:
            OpenAI: 設定されたAPIクライアント
        """
        client_params = {"api_key": self.config.api_key}

        # GeminiConfigの場合はOpenAI互換エンドポイントを設定
        if isinstance(self.config, GeminiConfig):
            client_params["base_url"] = (
                "https://generativelanguage.googleapis.com/v1beta/openai/"
            )

        return OpenAI(**client_params)

    def retrieve_answer(
        self, chat_history: list[Message], max_messages: int = 5
    ) -> ChatCompletion:
        """
        チャット履歴から回答を取得します。

        注意: この機能はトークン数ベースの制限から単純なメッセージ件数ベースの制限に移行したため、
        内部処理が形骸化されました。現在はmax_messagesパラメータを使用して直近の指定件数のみを
        保持する方式に置き換えられています。

        Args:
            chat_history (list[Message]): チャット履歴メッセージのリスト
            max_messages (int, optional): 保持する最大メッセージ件数。デフォルト値は5。

        Returns:
            ChatCompletion: OpenAI形式のチャット完了レスポンス
        """
        cut_down_history = cut_down_chat_history(chat_history, max_messages)

        # 空のチャット履歴の場合はエラー
        if not cut_down_history:
            raise ValueError("Chat history cannot be empty")

        return self.client.chat.completions.create(
            model=self.config.model,
            messages=[x.to_dict() for x in cut_down_history],
        )


class LlmCompletionStreamingService(LlmService):
    """
    OpenAIとGeminiの両方に対応したストリーミングLLM完了サービス。
    OpenAIのAPIインターフェースを使用してGeminiモデルにもストリーミングアクセスできます。
    """

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config
        self.client = self._initialize_client()

    def _initialize_client(self) -> OpenAI:
        """
        APIクライアントを初期化します。
        GeminiConfigの場合はOpenAI互換エンドポイントを使用します。

        Returns:
            OpenAI: 設定されたAPIクライアント
        """
        client_params = {"api_key": self.config.api_key}

        # GeminiConfigの場合はOpenAI互換エンドポイントを設定
        if isinstance(self.config, GeminiConfig):
            client_params["base_url"] = (
                "https://generativelanguage.googleapis.com/v1beta/openai/"
            )

        return OpenAI(**client_params)

    def retrieve_answer(
        self, chat_history: list[Message], max_messages: int = 5
    ) -> Generator[StreamResponse, None, None]:
        """
        OpenAIのストリーミングレスポンスを処理し、応答をジェネレーターとして返します。

        Args:
            chat_history (list[Message]): チャット履歴
            max_messages (int, optional): 保持する最大メッセージ件数。デフォルト値は5。

        Returns:
            Generator[StreamResponse, None, None]:
                - `StreamResponse`はジェネレーターが`yield`するオブジェクト。
                - `None`（2つ目の型）はジェネレーターに対して値を送り込む型がないことを示します。
                - `None`（3つ目の型）はこのジェネレーターが停止時に明示的な`return`を行わないことを示します。
        """
        cut_down_history = cut_down_chat_history(chat_history, max_messages)

        # 空のチャット履歴の場合はエラー
        if not cut_down_history:
            raise ValueError("Chat history cannot be empty")

        stream = self.client.chat.completions.create(
            model=self.config.model,
            messages=[x.to_dict() for x in cut_down_history],
            stream=True,
        )
        for chunk in stream:
            delta_content = chunk.choices[0].delta.content
            finish_reason = chunk.choices[0].finish_reason
            yield StreamResponse(content=delta_content, finish_reason=finish_reason)

    def stream_chunks(
        self, chat_history: list[Message], max_messages: int = 5
    ) -> Generator[StreamResponse, None, None]:
        """
        チャット履歴に基づくストリーミングレスポンスを取得し、正常データおよび例外発生時のエラーメッセージを
        ストリーミング形式で返します。

        Args:
            chat_history (list[Message]): チャット履歴
            max_messages (int, optional): 保持する最大メッセージ件数。デフォルト値は5。

        Yields:
            StreamResponse:
                - ストリーミングレスポンスの通常のデータチャンク（正常時）。
                - 例外発生時には、エラーメッセージを含むレスポンス（`content` にエラー内容を含む）。

        Exceptions:
            例外はキャッチされ、ストリーミング形式でエラーメッセージとしてレスポンスに含まれます。

        Note:
            - このメソッドはジェネレーターとして実装されており、データを逐次的に処理および提供します。
            - 例外が発生した場合でも、ストリーミングの処理は中断されず、適切なエラーメッセージが生成されます。
            - リアルタイムでのデータ処理が求められるユースケース（例: Webアプリケーション、APIクライアント）で
              使用することを想定しています。

        See Also:
            - https://platform.openai.com/docs/api-reference/streaming
        """
        try:
            for chunk in self.retrieve_answer(chat_history, max_messages):
                yield chunk
        except Exception as e:
            yield StreamResponse(content=f"{str(e)}", finish_reason="stop")

    @staticmethod
    def streaming_from_generator(
        generator: Generator[StreamResponse, None, None],
    ) -> Generator[str, None, None]:
        """
        サーバー送信イベント形式（Server-Sent Events, SSE）としてジェネレーターからデータをストリームします。

        このメソッドは、`stream_chunks` などで生成されたデータジェネレーターを使用して、SSE形式のレスポンスを生成します。
        SSE形式では、各データチャンクが `data: ` プレフィックスで送られるため、リアルタイム更新を必要とするWebアプリケーションで
        使用することができます。

        Args:
            generator (Generator[StreamResponse, None, None]): チャンクデータを生成するジェネレーター。

        Yields:
            str: フォーマットされた文字列。各データは `data: チャンク\n\n` の形式。

        Example:
            以下のようなレスポンスが生成されます:
            ```
            data: こんにちは

            data: 天気は晴れです

            ```

        Server-Sent Events (SSE):
            SSEは、サーバーがクライアントに対してリアルタイムでデータを送信するためのシンプルなプロトコルです。
            HTTPでストリーミングレスポンスを実装する際に使用され、クライアントが簡単にデータを受信することが出来ます。

            主な特徴:
            - クライアントはサーバーとの接続を開き、サーバーはそのチャネルを通じてイベントを送信します。
            - Webブラウザ（JavaScript）では、`EventSource` APIを使用してデータを受信できます。

        References:
            - SSEに関する詳細: https://developer.mozilla.org/ja/docs/Web/API/Server-sent_events
            - OpenAIストリーミングAPI: https://platform.openai.com/docs/api-reference/streaming
        """
        for chunk in generator:
            yield f"data: {chunk.to_json()}\n\n"


class OpenAILlmDalleService(LlmService):
    """
    OpenAIのDALL-Eモデルを使用して画像生成を行うサービス。
    """

    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(api_key=self.config.api_key)

    def retrieve_answer(self, message: Message) -> ImagesResponse:
        """
        メッセージの内容に基づいて画像を生成します。

        Args:
            message (Message): 画像生成プロンプトを含むメッセージ

        Returns:
            ImagesResponse: 生成された画像のレスポンス
        """
        if not message or not message.content:
            raise ValueError("Message content cannot be empty for image generation")

        return self.client.images.generate(
            model=self.config.model,
            prompt=message.content,
            size="1024x1024",
            quality="standard",
            n=1,
        )


class OpenAILlmTextToSpeech(LlmService):
    """
    OpenAIのテキスト音声変換サービス。
    テキストを音声に変換します。
    """

    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(api_key=self.config.api_key)

    def retrieve_answer(self, message: Message):
        """
        テキストを音声に変換します。

        Args:
            message (Message): 音声に変換するテキストを含むメッセージ

        Returns:
            音声ファイルのレスポンス
        """
        if not message or not message.content:
            raise ValueError(
                "Message content cannot be empty for text-to-speech conversion"
            )

        return self.client.audio.speech.create(
            model=self.config.model,
            voice="alloy",
            input=message.content,
            response_format="mp3",
        )


class OpenAILlmSpeechToText(LlmService):
    """
    OpenAIの音声テキスト変換サービス。
    音声ファイルをテキストに変換します。
    """

    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config
        self.client = OpenAI(api_key=self.config.api_key)

    def retrieve_answer(self, file_path: str):
        """
        音声ファイルをテキストに変換します。

        Args:
            file_path (str): 変換する音声ファイルのパス（MEDIA_ROOTからの相対パス）

        Returns:
            音声のテキスト変換結果
        """
        if not file_path:
            raise ValueError("File path cannot be empty for speech-to-text conversion")

        full_path = os.path.join(MEDIA_ROOT, file_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Audio file not found at {full_path}")

        with open(full_path, "rb") as audio_file:
            return self.client.audio.transcriptions.create(
                model=self.config.model, file=audio_file
            )


class OpenAILlmRagService(LlmService):
    """OpenAI SDK 直接利用のシンプルな RAG 実装。

    - 埋め込み: OpenAI Embeddings API（デフォルト: text-embedding-3-small）
    - ベクトルストア: メモリ内（コサイン類似度）。
      TODO(persistence): 需要が出たら Chroma 等に永続化する。
    - 生成: OpenAI Chat Completions（`model` は呼び出し元設定を流用）。
    """

    MAX_CONTEXT_CHARS = 6000

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        documents: Sequence[Any] | None = None,
        n_results: int = 3,
        embedding_model: str = "text-embedding-3-small",
        system_template: str | None = None,
    ) -> None:
        super().__init__()
        self.model = model
        self.api_key = api_key
        self.n_results = n_results
        self.embedding_model = embedding_model
        self._client = OpenAI(api_key=self.api_key)

        # ドキュメントは page_content, metadata を持つことを想定。
        self._docs: list[Any] = list(documents or [])
        self._embeddings: list[list[float]] = []

        # 既存のプロンプト文面を流用
        self.system_template = (
            system_template
            or """
            以下の資料の注意点を念頭に置いて回答してください
            ・ユーザの質問に対して、できる限り根拠を示してください
            ・箇条書きで簡潔に回答してください。
            ---下記は資料の内容です---
            {summaries}

            Answer in Japanese:
            """
        ).strip()

        if self._docs:
            self._ensure_corpus_indexed()

    # --- public API ---
    def retrieve_answer(self, message: Any) -> dict:
        """質問に対する回答を返す。

        Args:
            message: 質問文字列、または `content` 属性を持つ VO（例: Message）。

        Returns:
            dict: {"answer": str, "sources": str, "source_documents": list, "warning": str|None}
        """
        question = self._extract_text(message)
        if not question:
            raise ValueError("Message content cannot be empty for RAG query")

        if not self._docs:
            # 空のコーパスに対する問い合わせ
            return {
                "answer": "知識ベースが空です。ドキュメントを登録してから再度お試しください。",
                "sources": "",
                "source_documents": [],
                "warning": None,
            }

        if not self._embeddings:
            self._ensure_corpus_indexed()

        # 質問をベクトル化
        q_vec = self._embed_texts([question])[0]

        # Top-k 類似ドキュメントを取得
        idxes = self._top_k_by_cosine(self._embeddings, q_vec, k=self.n_results)
        selected = [self._docs[i] for i in idxes]

        summaries = self._join_summaries(documents=selected)
        warning = None
        # 軽量な「長さアラート」: 文字数ベース。必要ならトークン化へ改良可。
        if len(summaries) > self.MAX_CONTEXT_CHARS:
            warning = f"summaries length {len(summaries)} exceeds {self.MAX_CONTEXT_CHARS} chars; trimmed."
            summaries = summaries[: self.MAX_CONTEXT_CHARS]

        # プロンプト構築（system + user）
        system_text = self.system_template.format(summaries=summaries)

        # New SDK 推奨の Responses API を使用
        # input には許可された型（Responses API の EasyInputMessageParam）で渡す
        system_msg: EasyInputMessageParam = {"role": "system", "content": system_text}
        user_msg: EasyInputMessageParam = {"role": "user", "content": question}

        response = self._client.responses.create(
            model=self.model,
            input=[system_msg, user_msg],
        )

        # output_text があればそれを優先
        answer = getattr(response, "output_text", None) or ""
        if not answer:
            # 後方互換の保険: choices 等にメッセージがあれば拾う
            try:
                # 一部実装では `response.output[0].content[0].text` 等の構造になる
                # 最低限の防御的パース（失敗しても空文字のまま）
                output = getattr(response, "output", None)
                if output and isinstance(output, list):
                    first = output[0]
                    content = getattr(first, "content", None)
                    if content and isinstance(content, list):
                        text = getattr(content[0], "text", None)
                        value = getattr(text, "value", None)
                        if isinstance(value, str):
                            answer = value
            except (AttributeError, TypeError, IndexError):
                # 期待しないレスポンス構造だった場合のみ捕捉し、警告として返す
                warning = (warning + " | " if warning else "") + "fallback_parse_error"

        # sources を人間可読にまとめる
        sources_list = []
        for d in selected:
            meta = getattr(d, "metadata", None) or {}
            src = meta.get("source") or meta.get("file") or str(meta)
            sources_list.append(str(src))
        sources = "\n".join(dict.fromkeys(sources_list))  # 重複排除を維持したまま

        return {
            "answer": answer,
            "sources": sources,
            "source_documents": selected,
            "warning": warning,
        }

    # --- corpus management ---
    def upsert_documents(self, documents: Iterable[Any]) -> None:
        """コーパスにドキュメントを追加・更新し、必要なら再ベクトル化。"""
        self._docs.extend(list(documents))
        self._ensure_corpus_indexed(recompute=True)

    # --- internals ---
    def _ensure_corpus_indexed(self, *, recompute: bool = False) -> None:
        if self._embeddings and not recompute:
            return
        texts = [getattr(d, "page_content", str(d)) for d in self._docs]
        self._embeddings = self._embed_texts(texts)

    def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """OpenAI Embeddings API でベクトル化。"""
        if not texts:
            return []
        resp = self._client.embeddings.create(
            model=self.embedding_model, input=list(texts)
        )
        return [d.embedding for d in resp.data]

    @staticmethod
    def _extract_text(message: Any) -> str:
        if message is None:
            return ""
        if isinstance(message, str):
            return message
        # Message VO 想定（.content）
        content = getattr(message, "content", None)
        return content if isinstance(content, str) else ""

    @staticmethod
    def _dot(a: Sequence[float], b: Sequence[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _norm(self, a: Sequence[float]) -> float:
        return (self._dot(a, a)) ** 0.5

    def _cosine(self, a: Sequence[float], b: Sequence[float]) -> float:
        na = self._norm(a)
        nb = self._norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return self._dot(a, b) / (na * nb)

    def _top_k_by_cosine(
        self, matrix: Sequence[Sequence[float]], vec: Sequence[float], k: int
    ) -> list[int]:
        scored = [(i, self._cosine(row, vec)) for i, row in enumerate(matrix)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [i for i, _ in scored[: max(k, 0)]]

    @staticmethod
    def _join_summaries(documents: Sequence[Any]) -> str:
        parts: list[str] = []
        for d in documents:
            text = getattr(d, "page_content", None)
            meta = getattr(d, "metadata", None) or {}
            source = meta.get("source") or ""
            if text:
                parts.append(f"[source: {source}]\n{text}")
        return "\n\n".join(parts)
