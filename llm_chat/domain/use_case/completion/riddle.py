from typing import Generator

from django.contrib.auth.models import User

from lib.llm.service.completion import LlmCompletionStreamingService
from lib.llm.valueobject.completion import RoleType, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    Riddle,
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
    ユーザーメッセージ側の `next_riddle_state` は、
    開始時は `[START]`、継続時は `[USER_INPUT, EVALUATE]` となります。

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
        """
        なぞなぞの1ターン（ユーザー入力 -> アシスタント返信）を実行します。

        Args:
            user (User): 実行ユーザー。
            content (str | None): ユーザーの入力内容。
            gender (Gender | None, optional): ユーザーの性別（回答のトーン調整用）。

        Returns:
            MessageDTO: 生成されたアシスタントのメッセージ。
                セッションが正常に進行中であれば、適切な `next_riddle_state` が付与されます。

        Raises:
            ValueError:
                - content が None の場合。
                - gender が None の場合。
                - セッションが既に終了している状態で、開始信号がないメッセージが送信された場合。

        Side Effects:
            - ユーザーメッセージとアシスタントメッセージを DB に保存します。
            - セッション開始シグナルの場合、過去の履歴をクリアします。
        """
        if gender is None:
            raise ValueError("gender is required for RiddleUseCase")

        (
            user_message,
            riddle_set,
            riddle_count,
            current_state,
            target_state,
            start_signals,
            _is_start,
        ) = _prepare_riddle_turn(
            repository=self.repository,
            config=self.config,
            max_turns=self.max_turns,
            user=user,
            content=content,
        )

        # アシスタント側では、状態をさらに進めて提示する
        # 開始時は、ユーザーが START をこなしたことを受けて [START, USER_INPUT] を提示する。
        # それ以外（回答時など）は、ユーザーが到達させた「次の状態」を起点として、さらにその先を履歴に含める
        # [target_state.next_state, target_state.next_state.next_state]
        if not current_state:
            target_states = [SessionState.START, SessionState.USER_INPUT]
        else:
            target_states = [
                target_state.next_state,
                target_state.next_state.next_state,
            ]

        chat_service = ChatService(self.config)
        assistant_message = chat_service.generate(
            user_message,
            use_case_type="Riddle",
            gender=gender,
            riddle_set=riddle_set,
            next_riddle_state=target_states,
        )

        # 6. 出題判定による状態補正
        answered_count = ChatLogRepository.count_answered_questions(user)
        if answered_count < riddle_count:
            # 問題がまだ残っている場合、次の状態をUSER_INPUTにする
            first_state = (
                SessionState.START if not current_state else SessionState.EVALUATE
            )
            target_states = [first_state, SessionState.USER_INPUT]
            assistant_message.next_riddle_state = SessionState.to_csv(target_states)

        # 7. 終了判定と評価
        if RiddleService.is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            # 終了処理（定型文付与、最終評価、メッセージクリーニング）
            assistant_message.content = RiddleService.report(
                assistant_message.content, riddle_count, user
            )

            # 終了状態を確定
            # [EVALUATE, FINISHED] となるように履歴を構成する
            target_states = [SessionState.EVALUATE, SessionState.FINISHED]
            assistant_message.next_riddle_state = SessionState.to_csv(target_states)

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=target_states,
        )


def _prepare_riddle_turn(
    repository: ChatLogRepository,
    config: OpenAIGptConfig | GeminiConfig,
    max_turns: int | None,
    user: User,
    content: str | None,
) -> tuple[
    MessageDTO, list[Riddle], int, SessionState | None, SessionState, list[str], bool
]:
    if content is None:
        raise ValueError("content cannot be None for RiddleUseCase")

    chat_history = ChatLogRepository.find_chat_history(user)
    last_message = chat_history[-1] if chat_history else None

    last_states = (
        SessionState.from_csv(last_message.next_riddle_state) if last_message else []
    )
    current_state = last_states[-1] if last_states else None

    start_signals = ["始めて", "はじめて", "スタート", "開始", "start"]
    is_start = any(sig in content for sig in start_signals)

    if is_start:
        ChatLogRepository.clear_all()
        current_state = None
    elif current_state == SessionState.FINISHED:
        raise ValueError(
            "セッションが終了しています。画面上の「なぞなぞの開始」を押してやりなおしてください。"
        )

    riddle_set = RiddleService.get_riddle_set(max_turns)
    riddle_count = len(riddle_set)

    target_state = current_state if current_state else SessionState.START
    if not current_state:
        target_states = [target_state]
    else:
        target_states = [target_state, target_state.next_state]

    user_message = MessageDTO(
        user=user,
        role=RoleType.USER,
        content=content,
        model_name=config.model,
        use_case_type=UseCaseType.RIDDLE,
        next_riddle_state=SessionState.to_csv(target_states),
    )
    saved = repository.insert(user_message)
    if saved:
        user_message.id = saved.id

    if not is_start:
        answered_count = ChatLogRepository.count_answered_questions(user)
        question_index = answered_count - 1
        if 0 <= question_index < riddle_count:
            riddle = riddle_set[question_index]
            evaluation = RiddleService.evaluate_turn(
                config=config,
                question=riddle.question,
                answer=riddle.answer,
                user_answer=content,
            )
            if evaluation:
                score_line = RiddleService.format_turn_scores(evaluation)
                ChatLogRepository.update_riddle_scores(
                    message_id=user_message.id,
                    scores=evaluation.model_dump(),
                    append_text=score_line,
                )

    return (
        user_message,
        riddle_set,
        riddle_count,
        current_state,
        target_state,
        start_signals,
        is_start,
    )


class RiddleStreamingUseCase(UseCase):
    """
    なぞなぞセッションのストリーミング版ユースケース。
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
    ) -> Generator[StreamResponse, None, None]:
        if gender is None:
            raise ValueError("gender is required for RiddleStreamingUseCase")
        (
            user_message,
            riddle_set,
            _riddle_count,
            _current_state,
            _target_state,
            _start_signals,
            _is_start,
        ) = _prepare_riddle_turn(
            repository=self.repository,
            config=self.config,
            max_turns=self.max_turns,
            user=user,
            content=content,
        )

        chat_history = ChatService.get_chat_history(
            user_message,
            use_case_type=UseCaseType.RIDDLE,
            gender=gender,
            riddle_set=riddle_set,
        )

        return LlmCompletionStreamingService(self.config).retrieve_answer(
            [chat_log.to_message() for chat_log in chat_history]
        )

    def save(self, user: User, content: str) -> None:
        if not content:
            raise ValueError("content is required for RiddleStreamingUseCase")

        chat_history = ChatLogRepository.find_chat_history(user)
        last_message = chat_history[-1] if chat_history else None

        if not last_message or last_message.role != RoleType.USER:
            raise ValueError("No user message available for streaming save")

        last_states = SessionState.from_csv(last_message.next_riddle_state) or []
        current_state = last_states[0] if len(last_states) >= 2 else None

        if current_state is None:
            target_states = [SessionState.START, SessionState.USER_INPUT]
        else:
            target_states = [
                current_state.next_state,
                current_state.next_state.next_state,
            ]

        assistant_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=SessionState.to_csv(target_states),
        )

        riddle_set = RiddleService.get_riddle_set(self.max_turns)
        riddle_count = len(riddle_set)

        answered_count = ChatLogRepository.count_answered_questions(user)
        if answered_count < riddle_count:
            first_state = (
                SessionState.START if current_state is None else SessionState.EVALUATE
            )
            target_states = [first_state, SessionState.USER_INPUT]
            assistant_message.next_riddle_state = SessionState.to_csv(target_states)

        start_signals = ["始めて", "はじめて", "スタート", "開始", "start"]
        if RiddleService.is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            assistant_message.content = RiddleService.report(
                assistant_message.content, riddle_count, user
            )
            target_states = [SessionState.EVALUATE, SessionState.FINISHED]
            assistant_message.next_riddle_state = SessionState.to_csv(target_states)

        self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=target_states,
        )
