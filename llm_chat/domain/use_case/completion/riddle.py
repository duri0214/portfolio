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

        Side Effects:
            - ユーザーメッセージとアシスタントメッセージを DB に保存します。
            - セッション開始シグナルの場合、過去の履歴をクリアします。
        """
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

        # 4. 状態遷移（このターンの状態）の決定
        # target_state: 今回のユーザー入力が対応する「このターンの状態」
        # target_state.next_state: ユーザー入力を受けて進むべき「次の状態」
        # 最終的にユーザーメッセージには、
        # [target_state, target_state.next_state] という 2段階の状態履歴が保存されます。
        target_state = current_state if current_state else SessionState.START
        if not current_state:
            # 開始時（START）のユーザーメッセージは START のみに制限
            target_states = [target_state]
        else:
            target_states = [target_state, target_state.next_state]

        # 5. メッセージの生成
        # ユーザーメッセージには、今回のアクション（開始や入力）を紐付ける
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=self.config.model,
            next_riddle_state=target_states,
            use_case_type=UseCaseType.RIDDLE,
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

        # 5.5 出題判定による状態補正
        # アシスタントが次の質問を出している場合、つぎの状態をUSER_INPUTにする
        if "##### 質問" in assistant_message.content:
            # 正規化された履歴を作成
            if not current_state:
                # 開始時は [START, USER_INPUT]
                target_states = [SessionState.START, SessionState.USER_INPUT]
            else:
                # 継続時は [EVALUATE, USER_INPUT]
                target_states = [SessionState.EVALUATE, SessionState.USER_INPUT]

            assistant_message.next_riddle_state = SessionState.to_csv(target_states)

        # 6. 終了判定と評価
        if RiddleChatService.is_session_finished(
            user, assistant_message, riddle_count, start_signals
        ):
            # 終了定型文がなければ追加
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # 最終評価
            RiddleChatService.report(
                assistant_message, riddle_count, chat_service, user, riddle_set
            )

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
            next_riddle_state=target_states,
        )
