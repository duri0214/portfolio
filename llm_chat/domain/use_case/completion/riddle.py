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

        # 3. 次の状態を計算
        scheduled_state: SessionState | None = (
            current_state.next_state if current_state else None
        )

        # 3. 問題セットの取得
        riddle_set = RiddleChatService.get_riddle_set(self.max_turns)
        riddle_count = len(riddle_set)

        # 4. 状態遷移の記録（インジケータとして複数の状態を保持可能にする）
        states_history: list[SessionState] = []
        if scheduled_state and scheduled_state != SessionState.FINISHED:
            # 継続中の場合は次に進むべき状態を履歴に追加
            states_history.append(scheduled_state)
        elif scheduled_state == SessionState.FINISHED:
            # 終了済みの場合は終了状態を維持
            states_history.append(SessionState.FINISHED)
        else:
            # 履歴がなく、開始シグナルもない場合、または開始時の場合は START から開始
            scheduled_state = SessionState.START
            states_history = [scheduled_state]

        # 5. メッセージの生成
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=self.config.model,
            next_riddle_state=[scheduled_state] if scheduled_state else None,
            use_case_type=UseCaseType.RIDDLE,
        )

        # アシスタント側では、START の次は WAIT_ANSWER になる
        if not last_message or is_start:
            if scheduled_state:
                # ユーザーの入力（開始/回答）を受けて、
                # システム（アシスタント）側では「さらにその次（あさって）」の状態を提示する
                scheduled_state = scheduled_state.next_state
                states_history.append(scheduled_state)

        chat_service = ChatService(self.config)
        assistant_message = chat_service.generate(
            user_message,
            use_case_type="Riddle",
            gender=gender,
            riddle_set=riddle_set,
            next_riddle_state=[scheduled_state] if scheduled_state else None,
        )

        # 5.5 出題判定による状態補正
        # アシスタントが次の質問を出している場合、状態を強制的に回答待ちにする
        if "##### 質問" in assistant_message.content:
            # 既に最後が WAIT_ANSWER なら追加不要
            if states_history and states_history[-1] == SessionState.WAIT_ANSWER:
                pass
            else:
                # 評価フェーズを通過して回答待ちに到達したことを示す
                if SessionState.EVALUATE not in states_history:
                    states_history.append(SessionState.EVALUATE)

                # EVALUATE の次は本来 WAIT_REBUTTAL だが、
                # 次の問題が出ている場合はさらにその先（WAIT_ANSWER）へ飛ばす
                # EVALUATE -> WAIT_REBUTTAL (skipped) -> REEVALUATE (skipped) -> NEXT_QUESTION (skipped) -> START -> WAIT_ANSWER
                # 実質的には EVALUATE の次は WAIT_ANSWER として扱う
                if SessionState.WAIT_ANSWER not in states_history:
                    states_history.append(SessionState.WAIT_ANSWER)

            assistant_message.next_riddle_state = SessionState.to_csv(states_history)

        # 6. 終了判定と評価
        if RiddleChatService.is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            if SessionState.FINISHED not in states_history:
                states_history.append(SessionState.FINISHED)
            assistant_message.next_riddle_state = SessionState.to_csv(states_history)
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # クリーニングと評価の追加
            RiddleChatService.finalize_message(
                assistant_message, riddle_count, chat_service, user, riddle_set
            )

        # 最終的な状態履歴を保存
        final_states = states_history if states_history else None

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=final_states,
        )
