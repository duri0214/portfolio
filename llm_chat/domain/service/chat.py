from typing import Any
from django.contrib.auth.models import User
from django.http import HttpRequest

from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.valueobject.completion.riddle import GenderType
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class ChatDisplayService:
    """IndexViewなどの表示ロジックを担当するサービスクラス"""

    @staticmethod
    def get_initial_values(request: HttpRequest, login_user: User) -> dict[str, Any]:
        """
        フォームの初期値を決定します。

        以下の優先順位で `use_case_type` を決定します：
        1. なぞなぞが進行中の場合（最新のなぞなぞ履歴が未終了）："Riddle"
        2. セッションに保存された use_case_type がある場合：それを優先
        3. 過去のチャット履歴がある場合：最新のメッセージで使用されたモデルから推定
        4. 履歴がない場合：デフォルトの "OpenAIGpt"
        """
        initial = {}
        chat_history = ChatLogRepository.find_chat_history(user=login_user)

        # 1. なぞなぞが進行中の場合は、Riddleモードを優先
        if ChatDisplayService.is_riddle_active(chat_history):
            initial["use_case_type"] = UseCaseType.RIDDLE
            # なぞなぞ進行中もセッションから性別を復元
            riddle_gender = request.session.get("riddle_gender")
            if riddle_gender:
                initial["gender"] = riddle_gender
            return initial

        # 2. セッションから use_case_type を復元
        session_use_case_type = request.session.get("use_case_type")
        if session_use_case_type:
            initial["use_case_type"] = session_use_case_type
        else:
            last_log = chat_history[-1] if chat_history else None

            if last_log:
                # 3. 直近の use_case_type を優先的に使用
                # データベースに保存されている use_case_type を直接初期値として設定する
                initial["use_case_type"] = last_log.use_case_type
            else:
                initial["use_case_type"] = UseCaseType.OPENAI_GPT

        # 4. セッションから性別の初期値を取得
        riddle_gender = request.session.get("riddle_gender")
        if riddle_gender:
            initial["gender"] = riddle_gender
        else:
            initial["gender"] = GenderType.MAN.value

        return initial

    @staticmethod
    def is_riddle_active(chat_history: list) -> bool:
        """なぞなぞが進行中か判定します（最新の履歴がなぞなぞで未終了か）。"""
        if not chat_history:
            return False

        last_log = chat_history[-1]
        return (
            last_log.use_case_type == UseCaseType.RIDDLE
            and RiddleChatService.RIDDLE_END_MESSAGE not in (last_log.content or "")
        )
