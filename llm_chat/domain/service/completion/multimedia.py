import base64
import os
import secrets
from io import BytesIO
from pathlib import Path

import requests.exceptions
from PIL import Image

from config.settings import MEDIA_ROOT
from lib.llm.service.completion import (
    OpenAILlmImageService,
    OpenAILlmTextToSpeech,
    OpenAILlmSpeechToText,
)
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIImageService(BaseChatService):
    model_name = ModelName.GPT_IMAGE_1_MINI

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        """
        画像生成を行い、結果を保存してMessageDTOを返します。
        gpt-image-1-mini: 1024x1024, 1024x1536, 1536x1024, auto のいずれかしか生成できない。
        また、主に b64_json 形式でデータを返します。
        """
        if user_message.content is None:
            raise Exception("content is None")

        # API側で推奨サイズ(auto)を指定して生成
        answer = OpenAILlmImageService(self.config).retrieve_answer(
            user_message.to_message(), size="auto"
        )

        image_data = answer.data[0]
        try:
            if hasattr(image_data, "b64_json") and image_data.b64_json:
                # base64形式の場合
                raw_picture = BytesIO(base64.b64decode(image_data.b64_json))
            elif hasattr(image_data, "url") and image_data.url:
                # URL形式の場合
                response = requests.get(image_data.url)
                response.raise_for_status()
                raw_picture = BytesIO(response.content)
            else:
                raise Exception(
                    "画像データの取得に失敗しました（b64_jsonもurlも空です）"
                )

            resized_picture = Image.open(raw_picture).resize((128, 128))
            return self._create_assistant_message(
                user=user_message.user,
                content=user_message.content,
                use_case_type=UseCaseType.OPENAI_GPT,
                file_path=self.save(resized_picture),
            )
        except requests.exceptions.HTTPError as http_error:
            raise Exception(http_error)
        except requests.exceptions.ConnectionError as connection_error:
            raise Exception(connection_error)
        except Exception as e:
            raise Exception(e)

    @staticmethod
    def save(image: Image.Image) -> str:
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
        image.save(str(full_path))

        # 相対パスを返す
        return f"llm_chat/images/{random_filename}"


class OpenAITextToSpeechService(BaseChatService):
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
        return self._create_assistant_message(
            user=user_message.user,
            content=user_message.content,
            use_case_type=UseCaseType.OPENAI_GPT,
            file_path=self.save(response),
        )

    @staticmethod
    def save(response) -> str:
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


class OpenAISpeechToTextService(BaseChatService):
    model_name = ModelName.WHISPER_1

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        if user_message.file_path is None:
            raise Exception("file_path is None")
        full_path = Path(MEDIA_ROOT) / user_message.file_path
        if full_path.exists():
            response = OpenAILlmSpeechToText(self.config).retrieve_answer(
                file_path=user_message.file_path
            )
            return self._create_assistant_message(
                user=user_message.user,
                content=f"音声ファイルは「{response.text}」とテキスト化されました",
                use_case_type=UseCaseType.OPENAI_GPT,
            )

        raise Exception(f"音声ファイル {user_message.file_path} は存在しません")
