import os
from typing import Any, Generator

from django.contrib.auth.models import User
from django.http import HttpRequest

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
from llm_chat.domain.service.completion.riddle import RiddleService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    GenderType,
    Riddle,
    SessionState,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class ChatDisplayService:
    """
    IndexViewなどの表示ロジックを担当するサービスクラス。

    Attributes:
        REGULAR_CHAT_EXCLUDED_USE_CASE_TYPES:
            通常チャット画面から分離する専用ユースケース。
    """

    REGULAR_CHAT_EXCLUDED_USE_CASE_TYPES = (UseCaseType.ROKUNOHE_MINUTES_RAG,)

    @staticmethod
    def get_regular_chat_history(login_user: User) -> list[MessageDTO]:
        """
        通常チャット画面に表示する履歴を取得します。

        六戸町会議録RAGは専用画面で扱うため、通常チャット画面からは除外します。
        """
        return ChatLogRepository.find_chat_history(
            user=login_user,
            excluded_use_case_types=(
                ChatDisplayService.REGULAR_CHAT_EXCLUDED_USE_CASE_TYPES
            ),
        )

    @staticmethod
    def get_initial_values(request: HttpRequest, login_user: User) -> dict[str, Any]:
        """
        フォームの初期値を決定します。

        以下の優先順位で `use_case_type` を決定します：
        1. なぞなぞが進行中の場合（最新のなぞなぞ履歴が未終了）："Riddle"
        2. セッションに保存された use_case_type がある場合：それを優先
        3. 過去のチャット履歴がある場合：最新のメッセージで使用されたモデルから推定
        4. 履歴がない場合：デフォルトの "OpenAIGptStreaming"
        """
        initial = {}
        chat_history = ChatDisplayService.get_regular_chat_history(login_user)

        if ChatDisplayService.is_riddle_active(chat_history):
            initial["use_case_type"] = UseCaseType.RIDDLE
            riddle_gender = request.session.get("riddle_gender")
            if riddle_gender:
                initial["gender"] = riddle_gender
            return initial

        session_use_case_type = request.session.get("use_case_type")
        if (
            session_use_case_type
            and session_use_case_type
            not in ChatDisplayService.REGULAR_CHAT_EXCLUDED_USE_CASE_TYPES
        ):
            initial["use_case_type"] = session_use_case_type
        else:
            last_log = chat_history[-1] if chat_history else None
            initial["use_case_type"] = (
                last_log.use_case_type if last_log else UseCaseType.OPENAI_GPT_STREAMING
            )

        riddle_gender = request.session.get("riddle_gender")
        if riddle_gender:
            initial["gender"] = riddle_gender
        else:
            initial["gender"] = GenderType.MAN.value

        rag_pdf_id = request.session.get("rag_pdf_id")
        if rag_pdf_id:
            initial["rag_pdf"] = rag_pdf_id

        return initial

    @staticmethod
    def is_riddle_active(chat_history: list) -> bool:
        """
        なぞなぞが進行中か判定します。
        最新の履歴がなぞなぞモード（UseCaseType.RIDDLE）であり、 かつ
        AIからの終了定型文（RiddleService.RIDDLE_END_MESSAGE）が含まれていない場合に
        「進行中（アクティブ）」とみなされます。

        フロントエンドでは、この判定結果に基づきボタンの色（黄色＝進行中、緑色＝開始前）が変化します。
        """
        if not chat_history:
            return False

        last_log = chat_history[-1]
        return (
            last_log.use_case_type == UseCaseType.RIDDLE
            and RiddleService.RIDDLE_END_MESSAGE not in (last_log.content or "")
        )


class ChatService(BaseChatService):
    """
    統合されたチャットサービス。

    OpenAI GPT や Google Gemini など、異なる LLM プロバイダーを統一された
    インターフェースで操作し、メッセージの生成や履歴管理を行います。

    Attributes:
        config (OpenAIGptConfig | GeminiConfig): 使用する LLM の設定。
        chat_history (list[MessageDTO]): 現在のセッションの会話履歴。
    """

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__(model_name=config.model)
        self.config = config
        self.chat_history: list[MessageDTO] = []

    @staticmethod
    def get_chat_history(
        user_message: MessageDTO,
        use_case_type: str = UseCaseType.OPENAI_GPT,
        gender: Gender = None,
        riddle_set: list[Riddle] | None = None,
    ) -> list[MessageDTO]:
        """
        チャット履歴を取得し必要に応じて初期プロンプトを追加する関数
        """

        if user_message.content is None:
            raise Exception("content is None")

        if use_case_type == UseCaseType.RIDDLE and gender is None:
            raise ValueError("gender is required for RiddleUseCase")

        # DBから履歴を取得
        chat_history = ChatLogRepository.find_chat_history(user_message.user)

        if not chat_history and use_case_type == UseCaseType.RIDDLE:
            # 初回
            chat_history = RiddleService.create_initial_prompt(
                user_message=user_message, gender=gender, riddle_set=riddle_set or []
            )
            # 初回ユーザーメッセージをDBに保存
            ChatLogRepository.insert(user_message)
        else:
            # 履歴に追加
            user_message.use_case_type = use_case_type
            chat_history.append(user_message)

            # 2回目以降
            if use_case_type == UseCaseType.RIDDLE:
                has_system = any(m.role == RoleType.SYSTEM for m in chat_history)
                if not has_system:
                    # アシスタントのメッセージ数から、現在何問目かを判定する
                    assistant_messages = [
                        m for m in chat_history if m.role == RoleType.ASSISTANT
                    ]
                    current_index = len(assistant_messages)

                    system_content = RiddleService.get_prompt(
                        gender=gender,
                        riddle_set=riddle_set or [],
                        current_index=current_index,
                    )

                    system_message = MessageDTO(
                        user=user_message.user,
                        role=RoleType.SYSTEM,
                        content=system_content,
                        use_case_type=UseCaseType.RIDDLE,
                    )
                    chat_history.insert(0, system_message)

        return chat_history

    def generate(
        self,
        user_message: MessageDTO,
        use_case_type: str = UseCaseType.OPENAI_GPT,
        gender: Gender | None = None,
        riddle_set: list[Riddle] | None = None,
        next_riddle_state: list[SessionState] | None = None,
    ) -> MessageDTO:
        """
        ユーザーメッセージを基に回答を生成します。
        """
        # なぞなぞモードはuse_case_typeが"Riddle"の場合に初期プロンプトを入れる
        self.chat_history = ChatService.get_chat_history(
            user_message,
            use_case_type=use_case_type,
            gender=gender,
            riddle_set=riddle_set,
        )

        chat_result = LlmCompletionService(self.config).retrieve_answer(
            [chat_log.to_message() for chat_log in self.chat_history]
        )

        return self._create_assistant_message(
            user=user_message.user,
            content=chat_result.answer,
            use_case_type=use_case_type,
            next_riddle_state=SessionState.to_csv(next_riddle_state),
        )

    def evaluate(self, login_user: User, riddle_set: list[Riddle]):
        """
        評価機能（Gemini/OpenAI共通）。
        評価結果を RiddleResponse として取得し、箇条書きテキストを返します。
        """
        task = RiddleService(self.config, self.chat_history)
        riddle_response = task.execute(login_user, riddle_set=riddle_set)

        # 箇条書きテキストを生成して返す
        return task.to_bullet_points(riddle_response)


class OpenAIStreamingService(BaseChatService):
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
        self.chat_history = ChatService.get_chat_history(
            user_message, use_case_type=UseCaseType.OPENAI_GPT
        )

        return LlmCompletionStreamingService(self.config).retrieve_answer(
            [x.to_message() for x in self.chat_history]
        )
