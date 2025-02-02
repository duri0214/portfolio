import os
from abc import ABC, abstractmethod
from typing import Generator

import tiktoken
from google import generativeai
from langchain.chains.qa_with_sources.retrieval import RetrievalQAWithSourcesChain
from langchain.prompts import (
    ChatPromptTemplate,
)
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import ChatCompletion

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.chat import Message
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from lib.llm.valueobject.rag import PdfDataloader


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


class OpenAILlmCompletionStreamService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(
        self, chat_history: list[Message]
    ) -> Generator[str, None, None]:
        cut_down_history = cut_down_chat_history(chat_history, self.config)
        stream = OpenAI(api_key=self.config.api_key).chat.completions.create(
            model=self.config.model,
            messages=[x.to_dict() for x in cut_down_history],
            temperature=self.config.temperature,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content


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


if __name__ == "__main__":
    from openai import AuthenticationError
    from lib.llm.valueobject.chat import RoleType

    service = OpenAILlmCompletionStreamService(
        config=OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-mini",
            temperature=0.7,  # 0-1の間で指定
            max_tokens=500,
        )
    )

    try:
        for stream_chunk in service.retrieve_answer(
            chat_history=[
                Message(role=RoleType.USER, content="今日の天気教えて"),
            ]
        ):
            # TODO: djangoのフロントで受け作れるかなー（たぶんページはわけたほうがよさそう）
            print(stream_chunk, end="")
    except AuthenticationError:
        # TODO: エラーが返ってくることが確認できたのでここでidentifyAPIErrorを使う（StreamingかidentifyAPIErrorが返る）
        print("Authentication failed: Please check your API key and try again.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
