import re
from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import GenderType, Gender
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RiddleUseCase(UseCase):
    """なぞなぞユースケース"""

    def __init__(
        self,
        config: OpenAIGptConfig | GeminiConfig,
        max_turns: int = RiddleChatService.DEFAULT_MAX_TURNS,
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

        chat_service = ChatService(self.config)

        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
        )

        # なぞなぞは明示的に use_case_type="Riddle" を指定
        assistant_message = chat_service.generate(
            user_message,
            use_case_type="Riddle",
            gender=gender,
            max_turns=self.max_turns,
        )

        # ユーザーの発言回数をカウント（generate() により今回の発言もDBに保存済み）
        chat_history = ChatLogRepository.find_chat_history(user)
        user_turns = [m for m in chat_history if m.role == RoleType.USER]
        turn_count = len(user_turns)

        # なぞなぞの終端処理
        # max_turns 回目の発言（質問2への回答）以降、または終了メッセージが含まれる場合
        if (
            turn_count >= self.max_turns
            or RiddleChatService.RIDDLE_END_MESSAGE in assistant_message.content
        ):
            # 終了メッセージが含まれていない場合は強制的に付与
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # 規定回数終了時に、もしLLMが余計な「質問3」などを出していたら除去を試みる
            if turn_count >= self.max_turns:
                # 「質問3」や「次の問題」といった文字列以降を、終了定型文を除いてカットする
                # 「第3問」「第３問」「問3」「問題3」など多様なパターンに対応
                # self.max_turns はユーザーの発言回数。問題数は self.max_turns - 1。
                # ユーザーが self.max_turns 回目の発言をした後は、
                # (self.max_turns - 1) + 1 = self.max_turns 問目の出題を阻止したい。
                target_num = self.max_turns
                extra_pattern = (
                    rf"(?:(?:それでは|では)?(?:次の|第|第 )?問題です。?|"
                    rf"質問{target_num}[:：]?|"
                    rf"第{target_num}問[:：]?|"
                    rf"問{target_num}[:：]?|"
                    rf"問題{target_num}[:：]?)"
                )
                if re.search(extra_pattern, assistant_message.content):
                    end_msg = RiddleChatService.RIDDLE_END_MESSAGE
                    if end_msg in assistant_message.content:
                        parts = assistant_message.content.split(end_msg)
                        # 余計な出題パターンで分割し、その前の部分（感想）を取得
                        main_content = re.split(extra_pattern, parts[0])[0].strip()
                        # 空行などを整理して再構成
                        assistant_message.content = (
                            main_content.rstrip() + "\n\n" + end_msg
                        )

            # 評価前に、今回のアシスタントメッセージを履歴に追加して文脈を完璧にする
            chat_service.chat_history.append(assistant_message)

            evaluation_text = chat_service.evaluate(login_user=user_message.user)
            assistant_message.content += evaluation_text

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
        )
