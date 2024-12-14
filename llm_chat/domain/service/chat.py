import os
import secrets
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path

import requests.exceptions
from PIL import Image
from django.contrib.auth.models import User

from config.settings import MEDIA_ROOT
from lib.llm.llm_service import (
    OpenAILlmCompletionService,
    OpenAILlmDalleService,
    OpenAILlmTextToSpeech,
    OpenAILlmSpeechToText,
    GeminiLlmCompletionService,
)
from lib.llm.valueobject.chat import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.chat import (
    ChatLogRepository,
)
from llm_chat.domain.valueobject.chat import MessageDTO, Gender


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


def create_initial_prompt(user: User, gender: Gender) -> list[MessageDTO]:
    history = [
        MessageDTO(
            user=user,
            role=RoleType.SYSTEM,
            content=get_prompt(gender),
            invisible=True,
        ),
        MessageDTO(
            user=user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            invisible=False,
        ),
    ]
    return history


class ChatService(ABC):
    def __init__(self):
        self.chatlog_repository = ChatLogRepository()

    @abstractmethod
    def generate(self, **kwargs):
        pass

    @abstractmethod
    def save(self, **kwargs) -> None:
        pass


class GeminiChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = GeminiConfig(
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="gemini-1.5-flash",
        )

    def generate(self, message: MessageDTO, gender: Gender) -> list[MessageDTO]:
        if message.content is None:
            raise Exception("content is None")

        chat_history = [
            MessageDTO(
                user=chatlog.user,
                role=RoleType[chatlog.role.upper()],
                content=chatlog.content,
                invisible=False,
                file_path=chatlog.file_path,
            )
            for chatlog in self.chatlog_repository.find_chat_history(message.user)
        ]
        latest_user_message = MessageDTO(
            user=message.user,
            role=message.role,
            content=message.content,
            invisible=False,
        )
        self.save(latest_user_message)
        chat_history.append(latest_user_message)

        response = GeminiLlmCompletionService(self.config).retrieve_answer(chat_history)

        latest_assistant = MessageDTO(
            user=message.user,
            role=RoleType.ASSISTANT,
            content=response.text,
            invisible=False,
        )
        self.save(latest_assistant)
        chat_history.append(latest_assistant)
        return chat_history

    def save(self, messages: MessageDTO | list[MessageDTO]) -> None:
        # TODO: listだけ受け取って、呼び出しのときに[]でいれさせればシンプルになるじゃん raiseもいらん
        if isinstance(messages, list):
            self.chatlog_repository.bulk_insert(messages)
        elif isinstance(messages, MessageDTO):
            self.chatlog_repository.insert(messages)
        else:
            raise ValueError(
                f"Unexpected type {type(messages)}. Expected MyChatCompletionMessage or list[MyChatCompletionMessage]."
            )


class OpenAIChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="gpt-4o-mini",
        )

    def generate(self, message: MessageDTO, gender: Gender) -> list[MessageDTO]:
        if message.content is None:
            raise Exception("content is None")

        chat_history = [
            MessageDTO(
                user=chatlog.user,
                role=RoleType[chatlog.role.upper()],
                content=chatlog.content,
                invisible=False,
                file_path=chatlog.file_path,
            )
            for chatlog in self.chatlog_repository.find_chat_history(message.user)
        ]
        if not chat_history:
            chat_history = create_initial_prompt(user=message.user, gender=gender)
            self.save(chat_history)

        # 初回はユーザのボタン押下などのトリガーで「プロンプト」と「なぞなぞスタート」の2行がinsertされる
        # 会話が始まっているならユーザの入力したチャットをinsertしてからChatGPTに全投げする
        # つまり、3以上あれば会話が始まっているだろうとみなせる
        if len(chat_history) > 2:
            latest_user_message = MessageDTO(
                user=message.user,
                role=message.role,
                content=message.content,
                invisible=False,
            )
            self.save(latest_user_message)
            chat_history.append(latest_user_message)

        answer = OpenAILlmCompletionService(self.config).retrieve_answer(chat_history)
        latest_assistant_message = MessageDTO(
            user=message.user,
            role=RoleType.ASSISTANT,
            content=answer.choices[0].message.content,
            invisible=False,
        )
        self.save(latest_assistant_message)
        chat_history.append(latest_assistant_message)

        if "本日はなぞなぞにご参加いただき" in latest_assistant_message.content:
            latest_user_message = MessageDTO(
                user=message.user,
                role=RoleType.USER,
                content="評価結果をjsonで出力してください",
                invisible=True,
            )
            self.save(latest_user_message)
            chat_history.append(latest_user_message)
            answer = OpenAILlmCompletionService(self.config).retrieve_answer(
                chat_history
            )
            latest_assistant = MessageDTO(
                user=message.user,
                role=RoleType.ASSISTANT,
                content=answer.choices[0].message.content,
                invisible=True,
            )
            self.save(latest_assistant)
            chat_history.append(latest_assistant)

        return chat_history

    def save(self, messages: MessageDTO | list[MessageDTO]) -> None:
        if isinstance(messages, list):
            self.chatlog_repository.bulk_insert(messages)
        elif isinstance(messages, MessageDTO):
            self.chatlog_repository.insert(messages)
        else:
            raise ValueError(
                f"Unexpected type {type(messages)}. Expected MyChatCompletionMessage or list[MyChatCompletionMessage]."
            )


class OpenAIDalleChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="dall-e-3",
        )

    def generate(self, message: MessageDTO):
        """
        画像urlの有効期限は1時間。それ以上使いたいときは保存する。
        dall-e-3: 1024x1024, 1792x1024, 1024x1792 のいずれかしか生成できない
        """
        if message.content is None:
            raise Exception("content is None")

        answer = OpenAILlmDalleService(self.config).retrieve_answer(message)
        image_url = answer.data[0].url
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            resized_picture = self.resize(picture=Image.open(BytesIO(response.content)))
            self.save(resized_picture, message)
        except requests.exceptions.HTTPError as http_error:
            raise Exception(http_error)
        except requests.exceptions.ConnectionError as connection_error:
            raise Exception(connection_error)
        except Exception as e:
            raise Exception(e)

    def save(self, picture: Image, message: MessageDTO) -> None:
        folder_path = Path(MEDIA_ROOT) / "images"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        random_filename = secrets.token_hex(5) + ".jpg"
        full_path = folder_path / random_filename
        message.file_path = "/media/images/" + random_filename
        picture.save(full_path)
        self.chatlog_repository.insert(message)

    @staticmethod
    def resize(picture: Image) -> Image:
        return picture.resize((128, 128))


class OpenAITextToSpeechChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="tts-1",
        )

    def generate(self, message: MessageDTO):
        if message.content is None:
            raise Exception("content is None")
        response = OpenAILlmTextToSpeech(self.config).retrieve_answer(message)
        self.save(response, message)

    def save(self, response, message: MessageDTO) -> None:
        folder_path = Path(MEDIA_ROOT) / "audios"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        random_filename = secrets.token_hex(5) + ".mp3"
        full_path = folder_path / random_filename
        message.file_path = "/media/audios/" + random_filename
        response.write_to_file(full_path)
        self.chatlog_repository.insert(message)


class OpenAISpeechToTextChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="whisper-1",
        )

    def generate(self, message: MessageDTO):
        if message.file_path is None:
            raise Exception("file_path is None")
        full_path = Path(MEDIA_ROOT) / message.file_path
        if full_path.exists():
            response = OpenAILlmSpeechToText(self.config).retrieve_answer(message)
            message.content = response.text
            print(f"\n音声ファイルは「{response.text}」とテキスト化されました\n")
            self.save(message)
        else:
            print(f"音声ファイル {message.file_path} は存在しません")

    def save(self, message: MessageDTO) -> None:
        self.chatlog_repository.update_file_path(message)
