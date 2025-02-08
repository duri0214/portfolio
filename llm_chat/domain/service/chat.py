import os
import secrets
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Generator

import requests.exceptions
from PIL import Image
from django.contrib.auth.models import User

from config.settings import MEDIA_ROOT, BASE_DIR
from lib.llm.llm_service import (
    OpenAILlmCompletionService,
    OpenAILlmCompletionStreamingService,
    OpenAILlmDalleService,
    OpenAILlmTextToSpeech,
    OpenAILlmSpeechToText,
    GeminiLlmCompletionService,
    OpenAILlmRagService,
)
from lib.llm.valueobject.chat import RoleType, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from lib.llm.valueobject.rag import PdfDataloader, RetrievalQAWithSourcesChainAnswer
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


def get_chat_history(
    message: MessageDTO,
    repository: ChatLogRepository,
    gender: Gender = None,
) -> list[MessageDTO]:
    """
    チャット履歴を取得し必要に応じて初期プロンプトを追加する関数

    この関数はユーザーの過去のチャット履歴を取得し、必要に応じて初期プロンプトを挿入します。
    主に次の流れで処理を行います：
    1. `message.content` が `None` の場合は例外をスローします。
    2. チャット履歴が存在する場合、それを取得します。
    3. チャット履歴が空であり、`gender` が指定されている場合は、
       なぞなぞモード用の初期プロンプトを生成し挿入します。
    4. 最新のユーザーメッセージを履歴に追加します。

    **特記事項**:
    初期プロンプト挿入は、なぞなぞモードの特別仕様です。このプロンプトには挨拶や、なぞなぞの開始案内が含まれます。

    :param message: 現在処理対象のユーザーからの入力メッセージ (MessageDTO)
    :param repository: チャット履歴を取得および保存するためのリポジトリ
    :param gender: なぞなぞモード用初期プロンプト生成のためのユーザーの性別（オプション）
    :raises Exception: メッセージが `content is None` の場合に例外をスロー
    :return: 過去の履歴や最新のユーザーメッセージを含むチャット履歴 (list[MessageDTO])
    """

    if message.content is None:
        raise Exception("content is None")

    chat_history = [
        MessageDTO(
            user=x.user, role=RoleType(x.role), content=x.content, invisible=False
        )
        for x in repository.find_chat_history(message.user)
    ]

    if not chat_history and gender is not None:
        chat_history = create_initial_prompt(user=message.user, gender=gender)
        repository.bulk_insert(chat_history)

    latest_user_message = MessageDTO(
        user=message.user,
        role=message.role,
        content=message.content,
        invisible=False,
    )
    repository.bulk_insert([latest_user_message])
    chat_history.append(latest_user_message)

    return chat_history


class ChatService(ABC):
    def __init__(self):
        self.repository = ChatLogRepository()

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

    def generate(self, message: MessageDTO) -> list[MessageDTO]:
        chat_history = get_chat_history(message, self.repository)

        response = GeminiLlmCompletionService(self.config).retrieve_answer(
            [x.to_message() for x in chat_history]
        )

        latest_assistant = MessageDTO(
            user=message.user,
            role=RoleType.ASSISTANT,
            content=response.text,
            invisible=False,
        )
        self.save([latest_assistant])
        chat_history.append(latest_assistant)
        return chat_history

    def save(self, messages: list[MessageDTO]) -> None:
        self.repository.bulk_insert(messages)


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
        chat_history = get_chat_history(message, self.repository, gender)

        answer = OpenAILlmCompletionService(self.config).retrieve_answer(
            [x.to_message() for x in chat_history]
        )
        latest_assistant_message = MessageDTO(
            user=message.user,
            role=RoleType.ASSISTANT,
            content=answer.choices[0].message.content,
            invisible=False,
        )
        self.save([latest_assistant_message])
        chat_history.append(latest_assistant_message)

        if "本日はなぞなぞにご参加いただき" in latest_assistant_message.content:
            latest_user_message = MessageDTO(
                user=message.user,
                role=RoleType.USER,
                content="評価結果をjsonで出力してください",
                invisible=True,
            )
            self.save([latest_user_message])
            chat_history.append(latest_user_message)
            answer = OpenAILlmCompletionService(self.config).retrieve_answer(
                [x.to_message() for x in chat_history]
            )
            latest_assistant = MessageDTO(
                user=message.user,
                role=RoleType.ASSISTANT,
                content=answer.choices[0].message.content,
                invisible=True,
            )
            self.save([latest_assistant])
            chat_history.append(latest_assistant)

        return chat_history

    def save(self, messages: list[MessageDTO]) -> None:
        self.repository.bulk_insert(messages)


class OpenAIChatStreamingService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="gpt-4o-mini",
        )

    def generate(self, message: MessageDTO) -> Generator[StreamResponse, None, None]:
        chat_history = get_chat_history(message, self.repository)

        return OpenAILlmCompletionStreamingService(self.config).retrieve_answer(
            [x.to_message() for x in chat_history]
        )

    def save(self, messages: list[MessageDTO]) -> None:
        pass


class OpenAIDalleChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="dall-e-3",
        )

    def generate(self, message: MessageDTO) -> list[MessageDTO]:
        """
        画像urlの有効期限は1時間。それ以上使いたいときは保存する。
        dall-e-3: 1024x1024, 1792x1024, 1024x1792 のいずれかしか生成できない
        """
        if message.content is None:
            raise Exception("content is None")

        answer = OpenAILlmDalleService(self.config).retrieve_answer(
            message.to_message()
        )
        image_url = answer.data[0].url
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            resized_picture = self.resize(picture=Image.open(BytesIO(response.content)))
            self.save(resized_picture, message)
            return [message]
        except requests.exceptions.HTTPError as http_error:
            raise Exception(http_error)
        except requests.exceptions.ConnectionError as connection_error:
            raise Exception(connection_error)
        except Exception as e:
            raise Exception(e)

    def save(self, picture: Image, message: MessageDTO) -> None:
        folder_path = Path(MEDIA_ROOT) / "llm_chat/images"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        random_filename = secrets.token_hex(5) + ".jpg"
        full_path = folder_path / random_filename
        message.file_path = "llm_chat/images/" + random_filename
        picture.save(str(full_path))
        message.to_entity().save()

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

    def generate(self, message: MessageDTO) -> list[MessageDTO]:
        if message.content is None:
            raise Exception("content is None")
        response = OpenAILlmTextToSpeech(self.config).retrieve_answer(
            message.to_message()
        )
        self.save(response, message)
        return [message]

    def save(self, response, message: MessageDTO) -> None:
        folder_path = Path(MEDIA_ROOT) / "llm_chat/audios"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        random_filename = secrets.token_hex(5) + ".mp3"
        full_path = folder_path / random_filename
        message.file_path = "llm_chat/audios/" + random_filename
        response.write_to_file(str(full_path))
        message.to_entity().save()


class OpenAISpeechToTextChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="whisper-1",
        )

    def generate(self, message: MessageDTO) -> list[MessageDTO]:
        if message.file_path is None:
            raise Exception("file_path is None")
        full_path = Path(MEDIA_ROOT) / message.file_path
        if full_path.exists():
            response = OpenAILlmSpeechToText(self.config).retrieve_answer(
                file_path=message.file_path
            )
            message.content = f"音声ファイルは「{response.text}」とテキスト化されました"
            self.save(message)
            return [message]

        raise Exception(f"音声ファイル {message.file_path} は存在しません")

    def save(self, message: MessageDTO) -> None:
        message.to_entity().save()


class OpenAIRagChatService(ChatService):
    def __init__(self):
        super().__init__()
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.5,
            max_tokens=4000,
            model="gpt-4o-mini",
        )

    def generate(self, message: MessageDTO) -> list[MessageDTO]:
        # Step1: User の質問を保存
        self.save(message)

        # Step2: langchainからの回答を保存
        file_path = (
            Path(BASE_DIR)
            / "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
        )
        answer_dict = OpenAILlmRagService(
            config=self.config,
            dataloader=PdfDataloader(str(file_path)),
        ).retrieve_answer(message.to_message())
        message.role = RoleType.ASSISTANT
        message.content = RetrievalQAWithSourcesChainAnswer(**answer_dict).answer
        self.save(message)
        return [message]

    def save(self, message: MessageDTO) -> None:
        message.to_entity().save()
