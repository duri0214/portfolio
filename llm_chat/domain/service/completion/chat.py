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
    from llm_chat.domain.service.completion.riddle import create_initial_prompt, get_prompt
    from llm_chat.domain.valueobject.completion.riddle import GenderType

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

    def evaluate(self, login_user):
        """
        評価機能（Gemini/OpenAI共通）。
        評価結果を RiddleResponse として取得し、箇条書きテキストを返します。
        """
        from llm_chat.domain.service.completion.riddle import RiddleTask

        # なぞなぞタスクを使用して構造化された評価結果を取得
        task = RiddleTask(self.config, self.chat_history)
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
        self.chat_history = get_chat_history(user_message, is_riddle=False)

        return LlmCompletionStreamingService(self.config).retrieve_answer(
            [x.to_message() for x in self.chat_history]
        )
