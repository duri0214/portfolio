import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv

# TODO(langchain-removal):
# LangChain 依存は隔離ゾーン経由に限定。新規コードでの直接利用は禁止。
from lib.llm.rag_core.langchain_impl import (
    RetrievalQAWithSourcesChain,
    ChatPromptTemplate,
    Chroma,
    ChatOpenAI,
    OpenAIEmbeddings,
)
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import ChatCompletion

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.completion import Message, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from lib.llm.valueobject.rag import PdfDataloader

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
    OpenAIモデルを使用した検索拡張生成（RAG）サービス。
    PDFなどのドキュメントに基づいた質問応答を実現します。

    See Also: https://python.langchain.com/docs/how_to/qa_sources/
    """

    def __init__(
        self,
        config: OpenAIGptConfig,
        dataloader: PdfDataloader,
        n_results: int = 3,
        embedding_model: str = "text-embedding-3-large",
    ):
        super().__init__()
        self.config = config
        self.dataloader = dataloader
        self.n_results = n_results
        self.embedding_model = embedding_model

        # プロンプトテンプレートの設定
        self.system_template = """
            以下の資料の注意点を念頭に置いて回答してください
            ・ユーザの質問に対して、できる限り根拠を示してください
            ・箇条書きで簡潔に回答してください。
            ---下記は資料の内容です---
            {summaries}

            Answer in Japanese:
        """
        messages = [
            ("system", self.system_template),
            ("human", "{question}"),
        ]
        self.prompt_template = ChatPromptTemplate.from_messages(messages)

    def _create_vectorstore(self) -> Chroma:
        """
        エンベディングとドキュメントを使用してベクトルストアを作成します。

        Note:
            ChromaDBのテレメトリー機能で "capture() takes 1 positional argument but 3 were given"
            エラーが発生する既知のバグがあります。
            docs: https://docs.trychroma.com/docs/overview/telemetry
            関連issue: https://github.com/chroma-core/chroma/issues/2640

        Returns:
            Chroma: 作成されたベクトルストア
        """
        if not self.dataloader or not self.dataloader.data:
            raise ValueError("Dataloader must contain valid documents")

        embeddings = OpenAIEmbeddings(model=self.embedding_model)

        return Chroma.from_documents(
            documents=self.dataloader.data,
            embedding=embeddings,
            persist_directory="./chroma_db",  # 永続化ディレクトリを指定
        )

    def retrieve_answer(self, message: Message) -> dict:
        """
        与えられたメッセージに基づいて、ドキュメントから関連情報を検索し回答を生成します。

        Args:
            message (Message): 質問を含むメッセージ

        Returns:
            dict: 回答と使用されたソースドキュメントを含む辞書
        """
        if not message or not message.content:
            raise ValueError("Message content cannot be empty for RAG query")

        # ベクトルストアの作成または再利用
        embeddings = OpenAIEmbeddings(model=self.embedding_model)
        docsearch = Chroma.from_texts(
            texts=[x.page_content for x in self.dataloader.data],
            embedding=embeddings,
            metadatas=[x.metadata for x in self.dataloader.data],
        )

        # LLMチェーンの作成
        chain = RetrievalQAWithSourcesChain.from_chain_type(
            llm=ChatOpenAI(model=self.config.model, api_key=self.config.api_key),
            chain_type="stuff",
            reduce_k_below_max_tokens=True,
            return_source_documents=True,
            retriever=docsearch.as_retriever(search_kwargs={"k": self.n_results}),
            chain_type_kwargs={"prompt": self.prompt_template},
        )

        return chain.invoke({"question": message.content})
