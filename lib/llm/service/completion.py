import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generator

import tiktoken
from dotenv import load_dotenv
from langchain.chains.qa_with_sources.retrieval import RetrievalQAWithSourcesChain
from langchain.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import ChatCompletion

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.chat import Message, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from lib.llm.valueobject.rag import PdfDataloader

# .env ファイルを読み込む
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def count_tokens(text: str) -> int:
    """
    与えられたテキストのトークン数をカウントします。

    この関数では、OpenAIのtiktokenライブラリを使用してトークン数をカウントしています。
    適切なエンコーディングを取得するため、特定のモデル名ではなく "o200k_base" を直接使用します。
    使用するエンコーディングは、与えられたテキストに対するトークンIDの配列（例：[15496, 2159, 0]）を返します。
    この配列の長さは、テキスト内のトークンの数を意味します。

    引数:
        text (str): トークン数を数えるテキスト。

    戻り値:
        int: テキスト内のトークン数。

    See Also: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
    """
    if not text:
        return 0

    encoding = tiktoken.get_encoding("o200k_base")
    tokens = encoding.encode(text)
    return len(tokens)


def cut_down_chat_history(
    chat_history: list[Message], config: OpenAIGptConfig | GeminiConfig
) -> list[Message]:
    """
    チャット履歴のメッセージリストを削減し、トークンの総数が config で指定した max_tokens を超えないようにします。

    この関数では、発生の逆順にメッセージを走査し、それらのトークン数を合計します。
    それが max_tokens を超えたとき、チャット履歴の早い部分をカットオフします。

    Args:
        chat_history (list[Message]): チャット履歴メッセージのリスト。
        config (OpenAIGptConfig | GeminiConfig): モデルの設定。max_tokens を含みます。

    Returns:
        list[Message]: 削減されたチャット履歴メッセージのリスト。
    """
    if not chat_history:
        return []

    token_count = 0

    for i in range(len(chat_history) - 1, -1, -1):  # 逆順にループ
        message = chat_history[i]
        token_count += count_tokens(message.content)
        if token_count > config.max_tokens:
            return chat_history[i + 1 :]  # 切り捨てた範囲の次から返す

    return chat_history


class LlmService(ABC):
    @abstractmethod
    def retrieve_answer(self, **kwargs):
        pass


class GeminiLlmCompletionService(LlmService):
    def __init__(self, config: GeminiConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, chat_history: list[Message]):
        # TODO: [-1]しか処理してないから、そのうち Gemini用のMessage にしたいね
        #  https://ai.google.dev/gemini-api/docs/get-started/tutorial?lang=python&hl=ja
        cut_down_history = cut_down_chat_history(chat_history, self.config)
        generativeai.configure(api_key=self.config.api_key)
        return generativeai.GenerativeModel(self.config.model).generate_content(
            cut_down_history[-1].content
        )


class OpenAILlmCompletionService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, chat_history: list[Message]) -> ChatCompletion:
        cut_down_history = cut_down_chat_history(chat_history, self.config)
        return OpenAI(api_key=self.config.api_key).chat.completions.create(
            model=self.config.model,
            messages=[x.to_dict() for x in cut_down_history],
            temperature=self.config.temperature,
        )


class OpenAILlmCompletionStreamingService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(
        self, chat_history: list[Message]
    ) -> Generator[StreamResponse, None, None]:
        """
        OpenAIのストリーミングレスポンスを処理し、応答をジェネレーターとして返します。

        Returns:
            Generator[StreamResponse, None, None]:
                - `StreamResponse`はジェネレーターが`yield`するオブジェクト。
                - `None`（2つ目の型）はジェネレーターに対して値を送り込む型がないことを示します。
                - `None`（3つ目の型）はこのジェネレーターが停止時に明示的な`return`を行わないことを示します。
        """

        cut_down_history = cut_down_chat_history(chat_history, self.config)
        stream = OpenAI(api_key=self.config.api_key).chat.completions.create(
            model=self.config.model,
            messages=[x.to_dict() for x in cut_down_history],
            temperature=self.config.temperature,
            stream=True,
        )
        for chunk in stream:
            delta_content = chunk.choices[0].delta.content
            finish_reason = chunk.choices[0].finish_reason
            yield StreamResponse(content=delta_content, finish_reason=finish_reason)

    def stream_chunks(
        self, chat_history: list[Message]
    ) -> Generator[StreamResponse, None, None]:
        """
        チャット履歴に基づくストリーミングレスポンスを取得し、正常データおよび例外発生時のエラーメッセージを
        ストリーミング形式で返します。

        Args:
            chat_history (list[Message]): チャット履歴

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
            for chunk in self.retrieve_answer(chat_history):
                yield chunk
        except Exception as e:
            yield StreamResponse(content=f"{str(e)}", finish_reason="stop")

    @staticmethod
    def streaming_from_generator(
        generator: Generator[StreamResponse, None, None]
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
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, message: Message) -> ImagesResponse:
        return OpenAI(api_key=self.config.api_key).images.generate(
            model=self.config.model,
            prompt=message.content,
            size="1024x1024",
            quality="standard",
            n=1,
        )


class OpenAILlmTextToSpeech(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, message: Message):
        return OpenAI(api_key=self.config.api_key).audio.speech.create(
            model=self.config.model,
            voice="alloy",
            input=message.content,
            response_format="mp3",
        )


class OpenAILlmSpeechToText(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, file_path: str):
        file_path = os.path.join(MEDIA_ROOT, file_path)
        audio = open(file_path, "rb")
        return OpenAI(api_key=self.config.api_key).audio.transcriptions.create(
            model=self.config.model, file=audio
        )


class OpenAILlmRagService(LlmService):
    def __init__(
        self, config: OpenAIGptConfig, dataloader: PdfDataloader, n_results: int = 3
    ):
        """
        See Also: https://python.langchain.com/docs/how_to/qa_sources/
        """
        super().__init__()
        self.config = config
        self.dataloader = dataloader
        self.n_results = n_results
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

    @staticmethod
    def _create_vectorstore(dataloader: PdfDataloader) -> Chroma:
        """
        Note: OpenAIEmbeddings runs on "text-embedding-ada-002"
        """
        embeddings = OpenAIEmbeddings()

        return Chroma.from_documents(
            documents=dataloader.data,
            embedding=embeddings,
            persist_directory=".",
        )

    def retrieve_answer(self, message: Message) -> dict:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        docsearch = Chroma.from_texts(
            texts=[x.page_content for x in self.dataloader.data],
            embedding=embeddings,
            metadatas=[x.metadata for x in self.dataloader.data],
        )
        chain = RetrievalQAWithSourcesChain.from_chain_type(
            llm=ChatOpenAI(temperature=0, model=self.config.model),
            chain_type="stuff",
            reduce_k_below_max_tokens=True,
            return_source_documents=True,
            retriever=docsearch.as_retriever(),
            chain_type_kwargs={"prompt": self.prompt_template},
        )

        return chain.invoke({"question": message.content})
