import os
import secrets
from io import BytesIO
from pathlib import Path

import requests.exceptions
from PIL import Image

from config.settings import MEDIA_ROOT
from lib.llm.service.completion import (
    OpenAILlmDalleService,
    OpenAILlmTextToSpeech,
    OpenAILlmSpeechToText,
)
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.service.base import BaseChatService
from llm_chat.domain.valueobject.chat import MessageDTO


class OpenAIDalleChatService(BaseChatService):
    model_name = ModelName.DALLE_3

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        """
        画像urlの有効期限は1時間。それ以上使いたいときは保存する。
        dall-e-3: 1024x1024, 1792x1024, 1024x1792 のいずれかしか生成できない
        """
        if user_message.content is None:
            raise Exception("content is None")

        answer = OpenAILlmDalleService(self.config).retrieve_answer(
            user_message.to_message()
        )
        image_url = answer.data[0].url
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            raw_picture = BytesIO(response.content)
            resized_picture = Image.open(raw_picture).resize((128, 128))
            file_path = self.save_picture(resized_picture)
            return self._create_assistant_message(
                user=user_message.user,
                content=user_message.content,
                is_riddle=False,
                file_path=file_path,
            )
        except requests.exceptions.HTTPError as http_error:
            raise Exception(http_error)
        except requests.exceptions.ConnectionError as connection_error:
            raise Exception(connection_error)
        except Exception as e:
            raise Exception(e)

    @staticmethod
    def save_picture(resized_picture) -> str:
        """
        画像を保存してファイルパスを返すメソッド
        """
        # 保存先フォルダとファイル名を準備
        folder_path = Path(MEDIA_ROOT) / "llm_chat/images"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)

        random_filename = secrets.token_hex(5) + ".jpg"
        full_path = folder_path / random_filename

        # 画像を保存
        resized_picture.save(str(full_path))

        # 相対パスを返す
        return f"llm_chat/images/{random_filename}"


class OpenAITextToSpeechChatService(BaseChatService):
    model_name = ModelName.TTS_1

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        if user_message.content is None:
            raise Exception("content is None")
        response = OpenAILlmTextToSpeech(self.config).retrieve_answer(
            user_message.to_message()
        )
        file_path = self.save_audio(response)
        return self._create_assistant_message(
            user=user_message.user,
            content=user_message.content,
            is_riddle=False,
            file_path=file_path,
        )

    @staticmethod
    def save_audio(response) -> str:
        """
        音声ファイルを保存してファイルパスを返すメソッド
        :param response: 音声データのレスポンス
        :return: 保存した音声ファイルの相対パス
        """
        # 保存先のフォルダとファイル名を準備
        folder_path = Path(MEDIA_ROOT) / "llm_chat/audios"
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)

        random_filename = secrets.token_hex(5) + ".mp3"
        full_path = folder_path / random_filename

        # 音声データを保存
        response.write_to_file(str(full_path))

        # 相対パスを返す
        return f"llm_chat/audios/{random_filename}"


class OpenAISpeechToTextChatService(BaseChatService):
    model_name = ModelName.WHISPER_1

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, assistant_message: MessageDTO) -> MessageDTO:
        if assistant_message.file_path is None:
            raise Exception("file_path is None")
        full_path = Path(MEDIA_ROOT) / assistant_message.file_path
        if full_path.exists():
            response = OpenAILlmSpeechToText(self.config).retrieve_answer(
                file_path=assistant_message.file_path
            )
            return self._create_assistant_message(
                user=assistant_message.user,
                content=f"音声ファイルは「{response.text}」とテキスト化されました",
                is_riddle=False,
                file_path=assistant_message.file_path,
            )

        raise Exception(f"音声ファイル {assistant_message.file_path} は存在しません")
