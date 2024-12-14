from abc import ABC, abstractmethod

import tiktoken
from google import generativeai
from openai import OpenAI
from openai.types import ImagesResponse
from openai.types.chat import ChatCompletion

from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
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
