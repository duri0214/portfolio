from django.contrib.auth.models import User

from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    SessionState,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RiddleUseCase(UseCase):
    """
    なぞなぞセッションの進行を管理するユースケース。

    「問題の出題、回答の受取、評価、終了判定」という
    一連のなぞなぞゲームのフロー（ステートマシン）を制御します。
    ユーザーがメッセージを送信した際、現在の状態から「次の工程（フェーズ）」を計算し、
    アシスタントの返信メッセージに `next_riddle_state` として付与して保存します。
    ユーザーメッセージ側の `next_riddle_state` は常に `None` とし、
    状態の提示責任を常にシステム（アシスタント）側に集約します。

    Attributes:
        config (OpenAIGptConfig | GeminiConfig): LLMの設定（モデル名、温度など）。
        max_turns (int, optional): セッションの最大ターン数（問題数）。デフォルトは None。
    """

    def __init__(
        self,
        config: OpenAIGptConfig | GeminiConfig,
        max_turns: int | None = None,
    ):
        super().__init__()
        self.config = config
        self.max_turns = max_turns

    def execute(
        self, user: User, content: str | None, gender: Gender | None = None
    ) -> MessageDTO:
        if content is None:
            raise ValueError("content cannot be None for RiddleUseCase")

        if gender is None:
            raise ValueError("gender is required for RiddleUseCase")

        # 1. 履歴を取得し、現在の状態を判定
        chat_history = ChatLogRepository.find_chat_history(user)
        last_message = chat_history[-1] if chat_history else None

        last_states = (
            SessionState.from_csv(last_message.next_riddle_state)
            if last_message
            else []
        )
        current_state = last_states[-1] if last_states else None

        # 2. 開始判定と初期化
        start_signals = ["始めて", "はじめて", "スタート", "開始", "start"]
        is_start = any(sig in content for sig in start_signals)
        if is_start:
            ChatLogRepository.clear_all()
            current_state = None

        # 3. 問題セットの取得
        riddle_set = RiddleChatService.get_riddle_set(self.max_turns)
        riddle_count = len(riddle_set)

        # 4. 状態遷移（このターン終了後の予定状態）の決定
        # 最終的にアシスタント側のメッセージには、
        # [current_state.next_state, current_state.next_state.next_state] という
        # 2段階の状態履歴（states_history）が保存されます。
        next_state = current_state.next_state if current_state else SessionState.START
        states_history: list[SessionState] = [next_state]

        # 5. メッセージの生成
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=self.config.model,
            next_riddle_state=[scheduled_state] if scheduled_state else None,
            use_case_type=UseCaseType.RIDDLE,
        )

        chat_service = ChatService(self.config)
        assistant_message = chat_service.generate(
            user_message,
            use_case_type="Riddle",
            gender=gender,
            riddle_set=riddle_set,
            next_riddle_state=next_state.value if next_state else None,
        )

        # 6. 終了判定と評価
        if RiddleChatService.is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            assistant_message.next_riddle_state = SessionState.FINISHED.value
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # クリーニングと評価の追加
            RiddleChatService.finalize_message(
                assistant_message, riddle_count, chat_service, user, riddle_set
            )

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=assistant_message.next_riddle_state,
        )
