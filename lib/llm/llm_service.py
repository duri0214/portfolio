import json
import secrets
import time
from abc import ABC, abstractmethod

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
from openai.types import ImagesResponse, Batch
from openai.types.chat import ChatCompletion

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.chat import MessageChunk
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from lib.llm.valueobject.rag import PdfDataloader
from llm_chat.domain.valueobject.chat import MessageDTO


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
    chat_history: list[MessageDTO], config: OpenAIGptConfig | GeminiConfig
) -> list[MessageDTO]:
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

    for i, message in enumerate(list(reversed(chat_history))):
        token_count += count_tokens(message.content)
        if token_count > config.max_tokens:
            return chat_history[-i:]

    return chat_history


class LlmService(ABC):
    @abstractmethod
    def retrieve_answer(self, **kwargs):
        pass


class GeminiLlmCompletionService(LlmService):
    def __init__(self, config: GeminiConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, chat_history: list[MessageDTO]):
        # TODO: [-1]しか処理してないから、そのうち Gemini用のMessageDTO にしたいね
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

    def retrieve_answer(self, chat_history: list[MessageDTO]) -> ChatCompletion:
        cut_down_history = cut_down_chat_history(chat_history, self.config)
        return OpenAI(api_key=self.config.api_key).chat.completions.create(
            model=self.config.model,
            messages=[x.to_request().to_dict() for x in cut_down_history],
            temperature=self.config.temperature,
        )


class OpenAIBatchCompletionService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    @staticmethod
    def export_jsonl_file(chunks: list[MessageChunk]) -> str:
        """
        指定された MessageChunk リストを JSONL 形式に変換して、ローカルファイルとして保存します。

        JSONL 形式の各行には、1つのチャンク（MessageChunk）がシリアライズされた
        JSON エントリが含まれています。

        Args:
            chunks (list[MessageChunk]): JSONL形式に変換する対象のデータチャンクリスト。

        Returns:
            str: 作成された JSONL ファイルの絶対パス。

        Raises:
            RuntimeError: ファイルの作成やデータの書き込み中にエラーが発生した場合。

        Example:
            >>> chunks1 = [
            >>>     MessageChunk(...),
            >>>     MessageChunk(...),
            >>> ]
            >>> file_path1 = OpenAIBatchCompletionService.export_jsonl_file(chunks1)
            >>> print(f"File saved at: {file_path}")

        Note:
            作成されたファイルは一時的なもので、後続の処理が完了後に削除されることが想定されています。
        """
        file_name = f"export_{secrets.token_hex(5)}.jsonl"
        file_path = os.path.abspath(file_name)
        try:
            with open(file_path, "w", encoding="utf-8") as jsonl_file:
                for chunk in chunks:
                    json_entry = chunk.to_jsonl_entry()
                    jsonl_file.write(json.dumps(json_entry) + "\n")
        except Exception as e:
            raise RuntimeError(f"Failed to export JSONL file: {str(e)}")

        return file_path

    def upload_jsonl_file(self, chunks: list[MessageChunk]) -> str:
        """
        JSONLファイルをOpenAIにアップロードする。

        Args:
            chunks (list[MessageChunk]): アップロードするデータのチャンク。

        Returns:
            str: アップロードされたファイルのID。
        """
        jsonl_file_path = self.export_jsonl_file(chunks)

        try:
            with open(jsonl_file_path, "rb") as jsonl_file:
                uploaded_file = OpenAI(api_key=self.config.api_key).files.create(
                    file=jsonl_file, purpose="batch"
                )
            return uploaded_file.id
        finally:
            if os.path.exists(jsonl_file_path):
                os.remove(jsonl_file_path)

    def poll_file_status(
            self, file_id: str, poll_interval: int = 5, timeout: int = 30
    ) -> Batch:
        """
        ファイルのステータスをポーリングするためのメソッド。

        Args:
            file_id (str): アップロードされたファイルのID。
            poll_interval (int): ポーリング間隔（秒）。
            timeout (int): 最大待機時間（秒）。

        Returns:
        FilePollingStatus: ファイルの最終ステータス情報。

        Raises:
            TimeoutError: タイムアウトの場合。
        """
        start_time = time.time()

        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= timeout:
                break

            # ファイルのステータスをチェック
            print(1)
            batch = OpenAI(api_key=self.config.api_key).batches.retrieve(file_id)
            print(2)
            print(f"!!!{batch}")

            if batch.get("status") == "processed":  # 処理が完了した場合
                return batch
            elif batch.get("status") == "failed":  # 処理が失敗した場合
                raise RuntimeError(
                    f"File processing failed for file_id={file_id}: {batch.get("status")}"
                )

            time.sleep(poll_interval)  # 次のポーリングまで待つ

        # ループから抜ける場合はタイムアウト
        raise TimeoutError(
            f"File processing timed out after {timeout} seconds for file_id={file_id}."
        )

    def retrieve_answer(self, chunks: list[MessageChunk]) -> Batch:
        """
        チャット履歴をOpenAIバッチAPIで処理して結果を取得するメソッド。

        Args:
            chunks (list[MessageChunk]): 入力データ。

        Returns:
            dict: 処理結果。
        """
        # 1. JSONLファイルをアップロード
        uploaded_file_id = self.upload_jsonl_file(chunks)

        # 2. ファイル処理が完了するまでポーリング
        batch_file = self.poll_file_status(file_id=uploaded_file_id)
        print(f"{batch_file=}")

        # 3. 最終的なファイルステータスを返す
        return batch_file


class OpenAILlmDalleService(LlmService):
    def __init__(self, config: OpenAIGptConfig):
        super().__init__()
        self.config = config

    def retrieve_answer(self, message: MessageDTO) -> ImagesResponse:
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

    def retrieve_answer(self, message: MessageDTO):
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

    def retrieve_answer(self, message: MessageDTO):
        file_path = os.path.join(MEDIA_ROOT, message.file_path)
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

    def retrieve_answer(self, message: MessageDTO) -> dict:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        docsearch = Chroma.from_texts(
            texts=[x.page_content for x in self.dataloader.data],
            embedding=embeddings,
            metadatas=[x.metadata for x in self.dataloader.data],
        )
        chain = RetrievalQAWithSourcesChain.from_chain_type(
            llm=ChatOpenAI(temperature=0, model_name=self.config.model),
            chain_type="stuff",
            reduce_k_below_max_tokens=True,
            return_source_documents=True,
            retriever=docsearch.as_retriever(),
            chain_type_kwargs={"prompt": self.prompt_template},
        )

        return chain.invoke({"question": message.content})
