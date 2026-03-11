import os
from typing import Generator

from lib.llm.service.completion import (
    LlmCompletionService,
    LlmCompletionStreamingService,
)
from lib.llm.valueobject.completion import RoleType, StreamResponse
from lib.llm.valueobject.config import (
    OpenAIGptConfig,
    GeminiConfig,
    ModelName,
)
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import Gender
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.valueobject.completion.riddle import GenderType


class ChatService(BaseChatService):
    """統合されたチャットサービス（GeminiとOpenAI両対応）"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__(model_name=config.model)
        self.config = config
        self.chat_history: list[MessageDTO] = []

    @staticmethod
    def get_chat_history(
        user_message: MessageDTO, use_case_type: str = "OpenAIGpt", gender: Gender = None
    ) -> list[MessageDTO]:
        """
        チャット履歴を取得し必要に応じて初期プロンプトを追加する関数

        この関数はユーザーの過去のチャット履歴を取得し、必要に応じて初期プロンプトを挿入します。
        主に次の流れで処理を行います：
        1. `message.content` が `None` の場合は例外をスローします。
        2. チャット履歴が存在する場合、それを取得します。
        3. チャット履歴が空であり、`use_case_type` が "Riddle" の場合は、
           なぞなぞモード用の初期プロンプトを生成し挿入します。
        4. 既存の履歴がある場合は、システムメッセージを先頭に動的に追加します。
        5. 最新のユーザーメッセージを履歴に追加します。

        **特記事項**:
        初期プロンプト挿入は、なぞなぞモードの特別仕様です。このプロンプトには挨拶や、なぞなぞの開始案内が含まれます。
        システムメッセージはDBには保存せず、LLMへのリクエスト時にのみ動的に追加されます。

        :param user_message: 現在処理対象のユーザーからの入力メッセージ (MessageDTO)
        :param use_case_type: ユースケースタイプ（"OpenAIGpt" または "Gemini" または "Riddle"）
        :param gender: なぞなぞモード用初期プロンプト生成のためのユーザーの性別（use_case_type="Riddle" の場合のみ使用）
        :raises Exception: メッセージが `content is None` の場合に例外をスロー
        :return: 過去の履歴や最新のユーザーメッセージを含むチャット履歴 (list[MessageDTO])
        """

        if user_message.content is None:
            raise Exception("content is None")

        if use_case_type == "Riddle" and gender is None:
            gender = Gender(GenderType.MAN)  # デフォルト

        # DBから履歴を取得（roleがstrで返ってくることを想定してRoleTypeで変換）
        chat_history = ChatLogRepository.find_chat_history(user_message.user)

        if not chat_history and use_case_type == "Riddle":
            # 初回：システムメッセージ（非保存）と初回ユーザーメッセージ（保存）を生成
            chat_history = RiddleChatService.create_initial_prompt(user_message=user_message, gender=gender)
        else:
            # 2回目以降：既存の履歴にシステムメッセージが含まれていない場合は動的に追加
            if use_case_type == "Riddle":
                has_system = any(m.role == RoleType.SYSTEM for m in chat_history)
                if not has_system:
                    system_message = MessageDTO(
                        user=user_message.user,
                        role=RoleType.SYSTEM,
                        content=RiddleChatService.get_prompt(gender),
                        use_case_type="Riddle",
                    )
                    chat_history.insert(0, system_message)

            # 最新のユーザーメッセージをDBに保存し、履歴に追加
            user_message.use_case_type = use_case_type
            ChatLogRepository.insert(user_message)
            chat_history.append(user_message)

        return chat_history

    def generate(
        self,
        user_message: MessageDTO,
        use_case_type: str = "OpenAIGpt",
        gender: Gender | None = None,
    ) -> MessageDTO:
        """
        ユーザーメッセージを基に回答を生成します。

        なぞなぞモードの場合は use_case_type="Riddle" と適切な gender を指定します。
        通常チャットの場合は use_case_type="OpenAIGpt" または "Gemini"（デフォルトは "OpenAIGpt"）を指定します。
        """
        # なぞなぞモードはuse_case_typeが"Riddle"の場合に初期プロンプトを入れる
        self.chat_history = ChatService.get_chat_history(
            user_message, use_case_type=use_case_type, gender=gender
        )

        chat_result = LlmCompletionService(self.config).retrieve_answer(
            [chat_log.to_message() for chat_log in self.chat_history]
        )

        return self._create_assistant_message(
            user=user_message.user,
            content=chat_result.answer,
            use_case_type=use_case_type,
        )

    def evaluate(self, login_user):
        """
        評価機能（Gemini/OpenAI共通）。
        評価結果を RiddleResponse として取得し、箇条書きテキストを返します。
        """
        task = RiddleChatService(self.config, self.chat_history)
        riddle_response = task.execute(login_user)

        # 箇条書きテキストを生成して返す
        return riddle_response.to_bullet_points()


class OpenAIChatStreamingService(BaseChatService):
    model_name = ModelName.GPT_5_MINI

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
        self.chat_history = ChatService.get_chat_history(user_message, use_case_type="OpenAIGpt")

        return LlmCompletionStreamingService(self.config).retrieve_answer(
            [x.to_message() for x in self.chat_history]
        )
