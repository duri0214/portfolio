import os
import secrets
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

import requests.exceptions
from PIL import Image
from django.contrib.auth.models import User
from google import generativeai
from google.generativeai.types import GenerateContentResponse
from openai import OpenAI
from openai.types.chat import (
    ChatCompletion,
)

from config.settings import MEDIA_ROOT
from llm_chat.domain.repository.chat import (
    ChatLogRepository,
)
from llm_chat.domain.valueobject.chat import MyChatCompletionMessage, Gender


def get_stored_chat_history(
    user_id: int, chatlog_repository: ChatLogRepository
) -> list[MyChatCompletionMessage]:
    chatlog_list = chatlog_repository.find_chatlog_by_user_id(user_id)
    history = [
        MyChatCompletionMessage(
            pk=chatlog.pk,
            user=chatlog.user,
            role=chatlog.role,
            content=chatlog.content,
            invisible=False,
            file_path=chatlog.file_path,
        )
        for chatlog in chatlog_list
    ]
    return history


def get_prompt(gender: Gender) -> str:
    return f"""
        あなたはなぞなぞコーナーの担当者です。

        #制約条件
        - 「なぞなぞスタート」と言われたら質問に移る前に、あいさつをします
        - 質問1のあとに質問2を行う。質問2が終わったら、感想を述べるとともに「本日はなぞなぞにご参加いただき、ありがとうございました。」と言って終わりましょう。判定結果は出力してはいけません
        - 質問1は「論理的思考力」評価します
        - 質問2は「洞察力」を評価します
        - scoreが70を超えたら、judgeが「合格」になる
        - {gender.name} の口調で会話を行う
        - 「評価結果をjsonで出力してください」と入力されたら、判定結果例のように判定結果を出力する

        #質問1
        - はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？

        #質問2
        - 私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？

        #判定結果例
        [{{"skill": "論理的思考力", "score": 50, "judge": "不合格"}},{{"skill": "洞察力", "score": 96, "judge": "合格"}}]
    """


def create_initial_prompt(user: User, gender: Gender) -> list[MyChatCompletionMessage]:
    history = [
        MyChatCompletionMessage(
            user=user,
            role="system",
            content=get_prompt(gender),
            invisible=True,
        ),
        MyChatCompletionMessage(
            user=user,
            role="user",
            content="なぞなぞスタート",
            invisible=False,
        ),
    ]
    return history


class LLMService(ABC):
    def __init__(self):
        self.chatlog_repository = ChatLogRepository()

    @abstractmethod
    def generate(self, **kwargs):
        pass

    @abstractmethod
    def post_to_gpt(self, **kwargs):
        pass

    @abstractmethod
    def save(self, **kwargs):
        pass


class GeminiService(LLMService):
    def __init__(self):
        super().__init__()

    def generate(
        self, my_chat_completion_message: MyChatCompletionMessage, gender: str
    ) -> list[MyChatCompletionMessage]:
        if my_chat_completion_message.content is None:
            raise Exception("content is None")

        chat_history = get_stored_chat_history(
            user_id=my_chat_completion_message.user.pk,
            chatlog_repository=self.chatlog_repository,
        )
        chat_history.append(
            self.save(
                MyChatCompletionMessage(
                    user=my_chat_completion_message.user,
                    role=my_chat_completion_message.role,
                    content=my_chat_completion_message.content,
                    invisible=False,
                )
            )
        )
        # TODO: Gemini用のMyChatCompletionMessageに詰め込みたい
        #  https://ai.google.dev/gemini-api/docs/get-started/tutorial?lang=python&hl=ja
        response = self.post_to_gpt(chat_history)
        latest_assistant = MyChatCompletionMessage(
            user=my_chat_completion_message.user,
            role="assistant",
            content=response.text,
            invisible=False,
        )
        chat_history.append(self.save(latest_assistant))
        return chat_history

    def post_to_gpt(
        self, chat_history: list[MyChatCompletionMessage]
    ) -> GenerateContentResponse:
        generativeai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = generativeai.GenerativeModel("gemini-1.5-flash")
        # TODO: 「会話」にしたいね
        response = model.generate_content(chat_history[-1].content)
        return response

    def save(
        self, messages: MyChatCompletionMessage | list[MyChatCompletionMessage]
    ) -> MyChatCompletionMessage | list[MyChatCompletionMessage]:
        if isinstance(messages, list):
            self.chatlog_repository.bulk_insert(messages)
        elif isinstance(messages, MyChatCompletionMessage):
            self.chatlog_repository.insert(messages)
        else:
            raise ValueError(
                f"Unexpected type {type(messages)}. Expected MyChatCompletionMessage or list[MyChatCompletionMessage]."
            )

        return messages


class OpenAIGptService(LLMService):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(
        self, my_chat_completion_message: MyChatCompletionMessage, gender: str
    ) -> list[MyChatCompletionMessage]:
        if my_chat_completion_message.content is None:
            raise Exception("content is None")

        chat_history = get_stored_chat_history(
            user_id=my_chat_completion_message.user.pk,
            chatlog_repository=self.chatlog_repository,
        )
        if not chat_history:
            chat_history = create_initial_prompt(
                user=my_chat_completion_message.user, gender=Gender(gender)
            )
            self.save(chat_history)

        # 初回はユーザのボタン押下などのトリガーで「プロンプト」と「なぞなぞスタート」の2行がinsertされる
        # 会話が始まっているならユーザの入力したチャットをinsertしてからChatGPTに全投げする
        # つまり、3以上あれば会話が始まっているだろうとみなせる
        if len(chat_history) > 2:
            chat_history.append(
                self.save(
                    MyChatCompletionMessage(
                        user=my_chat_completion_message.user,
                        role=my_chat_completion_message.role,
                        content=my_chat_completion_message.content,
                        invisible=False,
                    )
                )
            )
        response = self.post_to_gpt(chat_history)

        latest_assistant = MyChatCompletionMessage(
            user=my_chat_completion_message.user,
            role=response.choices[0].message.role,
            content=response.choices[0].message.content,
            invisible=False,
        )
        chat_history.append(self.save(latest_assistant))

        if "本日はなぞなぞにご参加いただき" in latest_assistant.content:
            chat_history.append(
                self.save(
                    MyChatCompletionMessage(
                        user=latest_assistant.user,
                        role="user",
                        content="評価結果をjsonで出力してください",
                        invisible=True,
                    )
                )
            )
            response = self.post_to_gpt(chat_history)

            latest_assistant = MyChatCompletionMessage(
                user=my_chat_completion_message.user,
                role=response.choices[0].message.role,
                content=response.choices[0].message.content,
                invisible=True,
            )
            chat_history.append(self.save(latest_assistant))

        return chat_history

    def post_to_gpt(
        self, chat_history: list[MyChatCompletionMessage]
    ) -> ChatCompletion:
        return self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[x.to_origin() for x in chat_history],
            temperature=0.5,
        )

    def save(
        self, messages: MyChatCompletionMessage | list[MyChatCompletionMessage]
    ) -> MyChatCompletionMessage | list[MyChatCompletionMessage]:
        if isinstance(messages, list):
            self.chatlog_repository.bulk_insert(messages)
        elif isinstance(messages, MyChatCompletionMessage):
            self.chatlog_repository.insert(messages)
        else:
            raise ValueError(
                f"Unexpected type {type(messages)}. Expected MyChatCompletionMessage or list[MyChatCompletionMessage]."
            )

        return messages


class OpenAIDalleService(LLMService):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(self, my_chat_completion_message: MyChatCompletionMessage):
        """
        画像urlの有効期限は1時間。それ以上使いたいときは保存する。
        dall-e-3: 1024x1024, 1792x1024, 1024x1792 のいずれかしか生成できない
        """
        if my_chat_completion_message.content is None:
            raise Exception("content is None")
        response = self.post_to_gpt(my_chat_completion_message.content)
        image_url = response.data[0].url
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            resized_picture = self.resize(picture=Image.open(BytesIO(response.content)))
            my_chat_completion_message = self.save(
                resized_picture,
                my_chat_completion_message,
            )
        except requests.exceptions.HTTPError as http_error:
            raise Exception(http_error)
        except requests.exceptions.ConnectionError as connection_error:
            raise Exception(connection_error)
        except Exception as e:
            raise Exception(e)

        return my_chat_completion_message

    def post_to_gpt(self, prompt: str):
        return self.client.images.generate(
            model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1
        )

    def save(
        self, picture: Image, my_chat_completion_message: MyChatCompletionMessage
    ) -> MyChatCompletionMessage:
        folder_path = Path(MEDIA_ROOT) / "images"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        # This generates a random string of 10 characters
        random_filename = secrets.token_hex(5) + ".jpg"
        relative_path_str = "/media/images/" + random_filename
        full_path = folder_path / random_filename
        my_chat_completion_message.file_path = relative_path_str
        picture.save(full_path)
        self.chatlog_repository.upsert(my_chat_completion_message)

        return my_chat_completion_message

    @staticmethod
    def resize(picture: Image) -> Image:
        return picture.resize((128, 128))


class OpenAITextToSpeechService(LLMService):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(self, my_chat_completion_message: MyChatCompletionMessage):
        if my_chat_completion_message.content is None:
            raise Exception("content is None")
        response = self.post_to_gpt(my_chat_completion_message.content)
        self.save(response, my_chat_completion_message)

    def post_to_gpt(self, text: str):
        return self.client.audio.speech.create(
            model="tts-1", voice="alloy", input=text, response_format="mp3"
        )

    def save(self, response, my_chat_completion_message: MyChatCompletionMessage):
        folder_path = Path(MEDIA_ROOT) / "audios"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        # This generates a random string of 10 characters
        random_filename = secrets.token_hex(5) + ".mp3"
        relative_path_str = "/media/audios/" + random_filename
        full_path = folder_path / random_filename
        my_chat_completion_message.file_path = relative_path_str
        response.write_to_file(full_path)
        self.chatlog_repository.upsert(my_chat_completion_message)

        return my_chat_completion_message


class OpenAISpeechToTextService(LLMService):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(self, my_chat_completion_message: MyChatCompletionMessage):
        if my_chat_completion_message.file_path is None:
            raise Exception("file_path is None")
        full_path = Path(MEDIA_ROOT) / my_chat_completion_message.file_path
        if full_path.exists():
            response = self.post_to_gpt(str(full_path))
            my_chat_completion_message.content = response.text
            print(f"\n音声ファイルは「{response.text}」とテキスト化されました\n")
            self.save(my_chat_completion_message)
        else:
            print(f"音声ファイル {my_chat_completion_message.file_path} は存在しません")

    def post_to_gpt(self, path_to_audio: str):
        audio = open(path_to_audio, "rb")
        return self.client.audio.transcriptions.create(model="whisper-1", file=audio)

    def save(self, my_chat_completion_message: MyChatCompletionMessage):
        self.chatlog_repository.upsert(my_chat_completion_message)
