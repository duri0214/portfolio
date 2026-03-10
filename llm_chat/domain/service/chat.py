import os
import json
import secrets
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Generator

import requests.exceptions
from PIL import Image
from django.contrib.auth.models import User

from config.settings import MEDIA_ROOT, BASE_DIR
from lib.llm.service.completion import (
    LlmCompletionService,
    LlmCompletionStreamingService,
    OpenAILlmDalleService,
    OpenAILlmTextToSpeech,
    OpenAILlmSpeechToText,
    OpenAILlmRagService,
    BaseLLMTask,
)
from lib.llm.valueobject.completion import RoleType, StreamResponse, Message
from lib.llm.valueobject.config import (
    OpenAIGptConfig,
    GeminiConfig,
    ModelName,
    OpenAiModel,
    GeminiModel,
)
from lib.llm.valueobject.rag import PdfDataloader
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.valueobject.chat import (
    MessageDTO,
    Gender,
    GenderType,
    RiddleResponse,
    RiddleEvaluation,
)


RIDDLE_END_MESSAGE = "本日はなぞなぞにご参加いただき、ありがとうございました。"


def get_prompt(gender: Gender) -> str:
    return f"""
        あなたはなぞなぞコーナーの担当者です。

        #制約条件
        - あなた自身で新しいなぞなぞを考えてはいけません。必ず以下の「##### 質問1」と「##### 質問2」を順番に出題してください。
        - 「なぞなぞスタート」または開始の合図をされたら、まずあいさつをし、続けて

        ##### 質問1
        を出題してください。
        - ユーザーが質問1に回答したら、その正誤には触れず、すぐに

        ##### 質問2
        を出題してください。
        - 質問2の回答を受け取ったら、感想を述べるとともに「{RIDDLE_END_MESSAGE}」と言って終了してください。
        - 判定結果（スコアや合否）は会話中に出力してはいけません。
        - {gender.name} の口調で会話を行ってください。
        - 「評価結果をjsonで出力してください」と入力された場合にのみ、指定のフォーマットで判定結果を出力してください。

        ##### 質問1
        - はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？

        ##### 質問2
        - 私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？

        #判定結果例
        [{{"viewpoint": "論理的思考力", "score": 50, "judge": "不合格"}},{{"viewpoint": "洞察力", "score": 96, "judge": "合格"}}]
    """


def create_initial_prompt(user_message: MessageDTO, gender: Gender) -> list[MessageDTO]:
    """
    初期プロンプト（システムメッセージと初回のユーザーメッセージ）を生成します。
    システムメッセージはDBに保存せず、初回ユーザーメッセージのみ保存します。
    """
    system_message = MessageDTO(
        user=user_message.user,
        role=RoleType.SYSTEM,
        content=get_prompt(gender),
        is_riddle=True,
    )
    first_user_message = MessageDTO(
        user=user_message.user,
        role=RoleType.USER,
        content=user_message.content,
        is_riddle=True,
    )
    # ユーザーメッセージのみDBに保存
    ChatLogRepository.insert(first_user_message)

    # システムメッセージを先頭に含めて返す
    return [system_message, first_user_message]


def get_chat_history(
    user_message: MessageDTO, is_riddle: bool = False, gender: Gender = None
) -> list[MessageDTO]:
    """
    チャット履歴を取得し必要に応じて初期プロンプトを追加する関数

    この関数はユーザーの過去のチャット履歴を取得し、必要に応じて初期プロンプトを挿入します。
    主に次の流れで処理を行います：
    1. `message.content` が `None` の場合は例外をスローします。
    2. チャット履歴が存在する場合、それを取得します。
    3. チャット履歴が空であり、`is_riddle` が True の場合は、
       なぞなぞモード用の初期プロンプトを生成し挿入します。
    4. 既存の履歴がある場合は、システムメッセージを先頭に動的に追加します。
    5. 最新のユーザーメッセージを履歴に追加します。

    **特記事項**:
    初期プロンプト挿入は、なぞなぞモードの特別仕様です。このプロンプトには挨拶や、なぞなぞの開始案内が含まれます。
    システムメッセージはDBには保存せず、LLMへのリクエスト時にのみ動的に追加されます。

    :param user_message: 現在処理対象のユーザーからの入力メッセージ (MessageDTO)
    :param is_riddle: なぞなぞモードかどうか
    :param gender: なぞなぞモード用初期プロンプト生成のためのユーザーの性別（is_riddle=True の場合のみ使用）
    :raises Exception: メッセージが `content is None` の場合に例外をスロー
    :return: 過去の履歴や最新のユーザーメッセージを含むチャット履歴 (list[MessageDTO])
    """

    if user_message.content is None:
        raise Exception("content is None")

    if is_riddle and gender is None:
        gender = Gender(GenderType.MAN)  # デフォルト

    # DBから履歴を取得（roleがstrで返ってくることを想定してRoleTypeで変換）
    chat_history = ChatLogRepository.find_chat_history(user_message.user)

    if not chat_history and is_riddle:
        # 初回：システムメッセージ（非保存）と初回ユーザーメッセージ（保存）を生成
        chat_history = create_initial_prompt(user_message=user_message, gender=gender)
    else:
        # 2回目以降：既存の履歴にシステムメッセージが含まれていない場合は動的に追加
        if is_riddle:
            has_system = any(m.role == RoleType.SYSTEM for m in chat_history)
            if not has_system:
                system_message = MessageDTO(
                    user=user_message.user,
                    role=RoleType.SYSTEM,
                    content=get_prompt(gender),
                    is_riddle=True,
                )
                chat_history.insert(0, system_message)

        # 最新のユーザーメッセージをDBに保存し、履歴に追加
        user_message.is_riddle = is_riddle
        ChatLogRepository.insert(user_message)
        chat_history.append(user_message)

    return chat_history


class BaseChatService(ABC):
    def __init__(self, model_name: OpenAiModel | GeminiModel | None = None):
        self.model_name = model_name

    @abstractmethod
    def generate(self, **kwargs):
        pass

    def _create_assistant_message(
        self, user: User, content: str, is_riddle: bool = False
    ) -> MessageDTO:
        return MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            model_name=self.model_name,
            is_riddle=is_riddle,
        )


class ChatService(BaseChatService):
    """統合されたチャットサービス（GeminiとOpenAI両対応）"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__(model_name=config.model)
        self.config = config
        self.chat_history: list[MessageDTO] = []

    def generate(
        self,
        user_message: MessageDTO,
        is_riddle: bool = False,
        gender: Gender | None = None,
    ) -> MessageDTO:
        """
        ユーザーメッセージを基に回答を生成します。

        なぞなぞモードの場合は is_riddle=True と適切な gender を指定します。
        通常チャットの場合は is_riddle=False（デフォルト）を指定します。
        """
        # なぞなぞモードはis_riddleがTrueの場合に初期プロンプトを入れる
        self.chat_history = get_chat_history(
            user_message, is_riddle=is_riddle, gender=gender
        )

        chat_result = LlmCompletionService(self.config).retrieve_answer(
            [chat_log.to_message() for chat_log in self.chat_history]
        )

        return self._create_assistant_message(
            user=user_message.user,
            content=chat_result.answer,
            is_riddle=is_riddle,
        )

    def evaluate(self, login_user: User) -> str:
        """
        評価機能（Gemini/OpenAI共通）。
        評価結果を RiddleResponse として取得し、箇条書きテキストを返します。
        """
        # なぞなぞタスクを使用して構造化された評価結果を取得
        task = RiddleTask(self.config, self.chat_history)
        riddle_response = task.execute(login_user)

        # 箇条書きテキストを生成して返す
        return riddle_response.to_bullet_points()


class RiddleTask(BaseLLMTask):
    """
    なぞなぞの評価タスク。
    LLMからの評価結果（JSON）をパースし、RiddleResponse型で返します。
    """

    def __init__(
        self,
        config: OpenAIGptConfig | GeminiConfig,
        chat_history: list[MessageDTO],
    ):
        self.config = config
        self.chat_history = chat_history

    def execute(self, login_user: User) -> RiddleResponse:
        """
        評価プロンプトを送信し、結果を RiddleResponse に変換します。
        """
        # 評価用のユーザーメッセージ（非表示）
        eval_message = Message(
            role=RoleType.USER,
            content="評価結果をjsonで出力してください。フォーマットは判定結果例に従うこと",
        )

        # メッセージ履歴を準備
        messages = [x.to_message() for x in self.chat_history]
        messages.append(eval_message)

        # LLM実行
        chat_result = LlmCompletionService(self.config).retrieve_answer(messages)
        raw_content = chat_result.answer

        # パース処理
        try:
            # LLMが ```json ... ``` で囲んでくる場合を考慮
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```"):
                lines = cleaned_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_content = "\n".join(lines).strip()

            eval_data = json.loads(cleaned_content)
            # eval_data はリスト形式 [{...}, {...}] と想定
            evaluations = [RiddleEvaluation(**item) for item in eval_data]

            return RiddleResponse(
                answer=raw_content,
                evaluations=evaluations,
                explanation="なぞなぞの評価結果です。",
            )
        except (json.JSONDecodeError, ValueError) as e:
            # パース失敗時のフォールバックまたはエラーハンドリング
            # ここで「残心」を持ってエラーを処理
            return RiddleResponse(
                answer=raw_content,
                evaluations=[],
                explanation=f"評価結果のパースに失敗しました: {str(e)}",
            )


class OpenAIChatStreamingService(BaseChatService):
    model_name: OpenAiModel = ModelName.GPT_5_MINI

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.chat_history = []
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(
        self, user_message: MessageDTO
    ) -> Generator[StreamResponse, None, None]:
        self.chat_history = get_chat_history(user_message, is_riddle=False)

        return LlmCompletionStreamingService(self.config).retrieve_answer(
            [x.to_message() for x in self.chat_history]
        )


class OpenAIDalleChatService(BaseChatService):
    model_name: OpenAiModel = ModelName.DALLE_3

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
            user_message.file_path = self.save_picture(resized_picture)
            return self._create_assistant_message(
                user=user_message.user,
                content=user_message.content,
                is_riddle=False,
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
    model_name: OpenAiModel = ModelName.TTS_1

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
        user_message.file_path = self.save_audio(response)
        return self._create_assistant_message(
            user=user_message.user,
            content=user_message.content,
            is_riddle=False,
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
    model_name: OpenAiModel = ModelName.WHISPER_1

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
            )

        raise Exception(f"音声ファイル {assistant_message.file_path} は存在しません")


class OpenAIRagChatService(BaseChatService):
    model_name: OpenAiModel = ModelName.GPT_5_MINI

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        # Step1: User の質問を保存
        ChatLogRepository.insert(user_message)

        # Step2: 回答を取得
        file_path = (
            Path(BASE_DIR)
            / "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
        )
        dataloader = PdfDataloader(str(file_path))
        rag_service = OpenAILlmRagService(
            model=self.config.model,
            api_key=self.config.api_key,
        )
        rag_service.upsert_documents(dataloader.data)
        response_dict = rag_service.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response_dict["answer"],
            is_riddle=False,
        )
