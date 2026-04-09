from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from config.settings import MEDIA_ROOT
from llm_chat.domain.service.completion.multimedia import (
    OpenAIImageService,
    OpenAITextToSpeechService,
    OpenAISpeechToTextService,
)
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIImageUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
        """
        OpenAIImageServiceを利用し、ユーザーからの入力テキスト（content）を基に画像を生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデル of instance
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            画像生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIImageUseCase")
        chat_service = OpenAIImageService()
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_IMAGE,
        )
        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_IMAGE,
            file_path=assistant_message.file_path,
        )


class OpenAITextToSpeechUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
        """
        OpenAITextToSpeechServiceを利用し、ユーザーからの入力テキスト（content）を基に音声を生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            音声生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAITextToSpeechUseCase")
        chat_service = OpenAITextToSpeechService()
        user_input_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_TEXT_TO_SPEECH,
        )
        assistant_message = chat_service.generate(user_input_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_TEXT_TO_SPEECH,
            file_path=assistant_message.file_path,
        )


class OpenAISpeechToTextUseCase(UseCase):
    def __init__(self, audio_file: UploadedFile):
        """
        初期化で音声ファイルを受け取り、保存処理を行い、後続処理で利用できるようにします。

        Args:
            audio_file (UploadedFile): Django のアップロードファイルオブジェクト

        Raises:
            ValueError: ファイルが指定されていない、または型が正しくない場合
            FileNotFoundError: 保存したファイルが確認できない場合
        """
        super().__init__()

        # ファイルを保存する（前準備）
        relative_path = f"llm_chat/audios/{audio_file.name}"
        save_path = Path(MEDIA_ROOT) / relative_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # ファイルの保存処理
        with open(save_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # 保存後にフルパスと相対パスを設定
        self.full_path = save_path
        if not self.full_path.exists():
            raise FileNotFoundError(
                f"指定された音声ファイル {self.full_path} は存在しません"
            )

        self.file_path = relative_path

    def execute(self, user: User, content: str) -> MessageDTO:
        """
        OpenAISpeechToTextServiceを利用し、ユーザーの最新の音声ファイルをテキストに変換します。
        contentパラメータは必ず 'N/A' であること。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str): この引数は必ず 'N/A' に固定

        Raises:
            ValueError: contentが 'N/A' でない場合

        Returns:
            音声をテキストに変換した結果
        """
        if content != "N/A":
            raise ValueError("content must be 'N/A' for OpenAISpeechToTextUseCase")

        chat_service = OpenAISpeechToTextService()
        user_message = self._insert_user_message(
            user=user,
            content=content,
            file_path=self.file_path,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_SPEECH_TO_TEXT,
        )

        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_SPEECH_TO_TEXT,
        )
