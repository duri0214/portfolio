import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generator, Iterable, Sequence

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.completion import (
    Message,
    StreamResponse,
    RagDocument,
    RagResponse,
)
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
    """
    OpenAI SDK と Chroma DB を使用した RAG (Retrieval-Augmented Generation) サービス。

    ドキュメントの埋め込みベクトルを作成し、Chroma DB に保存・検索することで、
    最新の知識や特定のコンテキストに基づいた回答を生成します。
    """

    MAX_CONTEXT_CHARS = 6000

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        persist_directory: str | None = None,
        collection_name: str = "portfolio_rag",
        n_results: int = 3,
        embedding_model: str = "text-embedding-3-small",
        system_template: str | None = None,
    ) -> None:
        """
        OpenAILlmRagService を初期化します。

        Args:
            model (str): 使用する OpenAI のチャットモデル名。
            api_key (str): OpenAI API キー。
            persist_directory (str | None, optional): Chroma DBの保存先ディレクトリ。
                未指定時は環境変数 `CHROMA_DB_PATH` の値を使用します。
                環境変数も設定されていない場合は、デフォルトでカレントディレクトリに `"chroma_db"` フォルダが作成されます。
                これにより、特別な設定なしですぐに動作し、かつ環境変数による柔軟なパス変更も可能です。
            collection_name (str, optional): Chroma 内でベクトルデータを管理するためのコレクション名。
                同じDB内でプロジェクトや用途ごとにデータを分離したい場合に、異なる名称を指定します。
            n_results (int, optional): 検索時に取得する上位ドキュメント数。デフォルトは3。
            embedding_model (str, optional): 埋め込みに使用するモデル名。デフォルトは "text-embedding-3-small"。
            system_template (str | None, optional): システムプロンプトのテンプレート。
                `{summaries}` プレースホルダを含む必要があります。
        """
        super().__init__()
        self.model = model
        self.api_key = api_key
        self.n_results = n_results
        self.embedding_model = embedding_model

        # Chroma DB の設定
        persist_path = persist_directory or os.getenv("CHROMA_DB_PATH", "chroma_db")
        self._client_db = chromadb.PersistentClient(
            path=persist_path, settings=Settings(allow_reset=True)
        )
        self._collection = self._client_db.get_or_create_collection(name=collection_name)
        self._client_openai = OpenAI(api_key=self.api_key)

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

    # --- public API ---
    def retrieve_answer(
        self, message: Any, where_filter: dict | None = None
    ) -> RagResponse:
        """
        質問に対する回答を RAG を用いて生成します。

        Args:
            message: 質問内容。文字列または content 属性を持つオブジェクト。
            where_filter (dict | None, optional): Chroma DB 検索時のフィルタ条件。

        Returns:
            RagResponse: 回答、ソース情報、参照ドキュメントを含むオブジェクト。
        """
        question = self._extract_text(message)
        if not question:
            raise ValueError("Message content cannot be empty for RAG query")

        # Chroma から検索
        results = self._collection.query(
            query_texts=[question], n_results=self.n_results, where=where_filter
        )

        # 検索結果を RagDocument VO のリストに変換
        selected: list[RagDocument] = []
        if results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                doc = RagDocument(
                    page_content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                )
                selected.append(doc)

        if not selected:
            return RagResponse(
                answer="該当する資料が見つかりませんでした。",
                sources="",
                source_documents=[],
                warning=None,
            )

        summaries = self._join_summaries(documents=selected)
        summaries, warning = self._validate_and_trim_context(
            summaries, self.MAX_CONTEXT_CHARS
        )

        # プロンプト構築（system + user）
        system_text = self.system_template.format(summaries=summaries)
        system_msg: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": system_text,
        }
        user_msg: ChatCompletionUserMessageParam = {
            "role": "user",
            "content": question,
        }

        response = self._client_openai.chat.completions.create(
            model=self.model,
            messages=[system_msg, user_msg],
        )
        answer = response.choices[0].message.content or ""

        # sources を人間可読にまとめる
        sources_list = []
        for d in selected:
            src = (
                d.metadata.get("source")
                or d.metadata.get("file")
                or str(d.metadata)
                or "unknown"
            )
            sources_list.append(str(src))
        sources = "\n".join(dict.fromkeys(sources_list))

        return RagResponse(
            answer=answer,
            sources=sources,
            source_documents=selected,
            warning=warning,
        )

    # --- corpus management ---
    def upsert_documents(self, documents: Iterable[Any]) -> None:
        """
        ドキュメントを Chroma DB に追加または更新します。

        Args:
            documents (Iterable[Any]): page_content と metadata 属性を持つドキュメントのリスト。
        """
        docs_list = list(documents)
        if not docs_list:
            return

        ids = []
        metadatas = []
        contents = []

        for i, d in enumerate(docs_list):
            content = getattr(d, "page_content", str(d))
            metadata = getattr(d, "metadata", {})
            # ID が指定されていない場合はメタデータの id またはインデックスを使用
            doc_id = metadata.get("id") or f"doc_{i}_{hash(content)}"

            ids.append(str(doc_id))
            metadatas.append(metadata)
            contents.append(content)

        self._collection.upsert(ids=ids, metadatas=metadatas, documents=contents)

    # --- internals ---
    @staticmethod
    def _validate_and_trim_context(
        summaries: str, max_chars: int
    ) -> tuple[str, str | None]:
        """
        コンテキストの長さをチェックし、必要に応じて切り詰めます。

        Args:
            summaries (str): 結合されたドキュメントの要約文字列。
            max_chars (int): 許容される最大文字数。

        Returns:
            tuple[str, str | None]: 切り詰められた文字列と、切り詰めが発生した場合の警告メッセージ。
        """
        warning = None
        if len(summaries) > max_chars:
            warning = f"summaries length {len(summaries)} exceeds {max_chars} chars; trimmed."
            summaries = summaries[:max_chars]
        return summaries, warning

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
    def _join_summaries(documents: Sequence[RagDocument]) -> str:
        parts: list[str] = []
        for d in documents:
            text = d.page_content
            source = d.metadata.get("source") or d.metadata.get("file") or "unknown"
            if text:
                parts.append(f"[source: {source}]\n{text}")
        return "\n\n".join(parts)
