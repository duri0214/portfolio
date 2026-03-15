import re
from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    Riddle,
    SessionState,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import RiddleQuestion


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
        current_state = (
            SessionState(last_message.next_riddle_state)
            if last_message and last_message.next_riddle_state
            else None
        )

        # 2. 開始判定と初期化
        start_signals = ["始めて", "はじめて", "スタート", "開始", "start"]
        is_start = any(sig in content for sig in start_signals)

        if is_start:
            ChatLogRepository.clear_all()
            current_state = SessionState.ASK_QUESTION

        # 3. 問題セットの取得
        riddle_set = self._get_riddle_set()
        riddle_count = len(riddle_set)

        # 4. 状態遷移
        next_state = self._get_next_state(current_state)

        # 5. メッセージの生成
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=None,
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
        if self._is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            assistant_message.next_riddle_state = SessionState.FINISHED.value
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # クリーニングと評価の追加
            self._finalize_assistant_message(
                assistant_message, riddle_count, chat_service, user, riddle_set
            )
            # 全体として空行が多すぎる場合があるので調整
            assistant_message.content = assistant_message.content.strip()

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=assistant_message.next_riddle_state,
        )

    def _get_riddle_set(self) -> list[Riddle]:
        db_questions = RiddleQuestion.objects.all().order_by("order")
        riddle_set = [
            Riddle(question=q.question_text, answer=q.answer_text) for q in db_questions
        ]
        if not riddle_set:
            raise ValueError(
                "なぞなぞの問題が登録されていません。管理画面から問題を登録してください。"
            )
        if self.max_turns is not None:
            riddle_set = riddle_set[: self.max_turns - 1]
        return riddle_set

    @staticmethod
    def _get_next_state(current_state: SessionState | None) -> SessionState | None:
        if current_state == SessionState.ASK_QUESTION:
            return SessionState.WAIT_ANSWER
        elif current_state == SessionState.WAIT_ANSWER:
            return SessionState.EVALUATE
        elif current_state == SessionState.EVALUATE:
            return SessionState.WAIT_REBUTTAL
        elif current_state == SessionState.WAIT_REBUTTAL:
            return SessionState.REEVALUATE
        elif current_state == SessionState.REEVALUATE:
            return SessionState.NEXT_QUESTION
        return current_state

    @staticmethod
    def _is_session_finished(
        user: User,
        assistant_message: MessageDTO,
        riddle_count: int,
        start_signals: list[str],
    ) -> bool:
        chat_history = ChatLogRepository.find_chat_history(user)
        answer_turns = [
            m
            for m in chat_history
            if m.role == RoleType.USER
            and not any(sig in m.content for sig in start_signals)
        ]
        return (
            len(answer_turns) >= riddle_count
            or RiddleChatService.RIDDLE_END_MESSAGE in assistant_message.content
        )

    @staticmethod
    def _finalize_assistant_message(
        assistant_message: MessageDTO,
        riddle_count: int,
        chat_service: ChatService,
        user: User,
        riddle_set: list[Riddle],
    ):
        # 終了メッセージのクリーニング
        next_riddle_num = riddle_count + 1
        extra_patterns = [
            rf"(?:(?:それでは|では)?(?:次の|第|第 )?問題です。?|質問{next_riddle_num}[:：]?|第{next_riddle_num}問[:：]?|問{next_riddle_num}[:：]?|問題{next_riddle_num}[:：]?)",
            r"続けて別のなぞなぞを出しましょうか？",
            r"このまま答えをたくさん出しますか？",
            r"別のなぞなぞを楽しみますか？",
            r"もっと続けますか？",
        ]
        combined_pattern = "|".join(extra_patterns)
        if re.search(combined_pattern, assistant_message.content):
            end_msg = RiddleChatService.RIDDLE_END_MESSAGE
            if end_msg in assistant_message.content:
                parts = assistant_message.content.split(end_msg)
                main_content = re.split(combined_pattern, parts[0])[0].strip()
                # 余計な見出し（#####）が残っている場合を削除
                main_content = re.sub(r"#####\s*$", "", main_content).strip()
                assistant_message.content = main_content.rstrip() + "\n\n" + end_msg

        # 評価の実行と追記
        chat_service.chat_history.append(assistant_message)
        evaluation_text = chat_service.evaluate(login_user=user, riddle_set=riddle_set)
        assistant_message.content += f"\n\n{evaluation_text}"
