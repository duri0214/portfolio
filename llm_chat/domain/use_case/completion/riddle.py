import re
from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import Gender, Riddle
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import RiddleQuestion


class RiddleUseCase(UseCase):
    """なぞなぞユースケース"""

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

        # DBから問題を読み込む
        db_questions = RiddleQuestion.objects.all().order_by("order")
        riddle_set = [
            Riddle(question=q.question_text, answer=q.answer_text) for q in db_questions
        ]

        # 問題が登録されていない場合は例外を投げる
        if not riddle_set:
            raise ValueError(
                "なぞなぞの問題が登録されていません。管理画面から問題を登録してください。"
            )

        # テスト互換性：max_turns が指定されている場合は riddle_set を切り詰める
        if self.max_turns is not None:
            riddle_set = riddle_set[: self.max_turns - 1]

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
            riddle_set=riddle_set,
        )

        # ユーザーの発言回数をカウント（generate() により今回の発言もDBに保存済み）
        chat_history = ChatLogRepository.find_chat_history(user)
        user_turns = [m for m in chat_history if m.role == RoleType.USER]
        turn_count = len(user_turns)
        riddle_count = len(riddle_set)

        # なぞなぞの終端処理
        # ユーザーの発言回数（スタート合図 + 各問題への回答回数）が (問題数 + 1) に達した場合、
        # またはAIのメッセージに終了定型文が含まれる場合に、評価フェーズへ移行する。
        # 例: 2問の場合、1回目:スタート、2回目:問1回答、3回目:問2回答（ここで全問終了）
        total_required_user_turns = riddle_count + 1
        if (
            turn_count >= total_required_user_turns
            or RiddleChatService.RIDDLE_END_MESSAGE in assistant_message.content
        ):
            # 終了メッセージが含まれていない場合は強制的に付与
            if RiddleChatService.RIDDLE_END_MESSAGE not in assistant_message.content:
                assistant_message.content += (
                    f"\n\n{RiddleChatService.RIDDLE_END_MESSAGE}"
                )

            # 規定回数終了時に、もしLLMが指示を無視して「存在しない次の問題（質問N+1）」を出していたら除去を試みる。
            # (リファクタリングによりプロンプトで制御しているが、モデルによっては出やすいため保険として残す)
            next_riddle_num = riddle_count + 1
            extra_pattern = (
                rf"(?:(?:それでは|では)?(?:次の|第|第 )?問題です。?|"
                rf"質問{next_riddle_num}[:：]?|"
                rf"第{next_riddle_num}問[:：]?|"
                rf"問{next_riddle_num}[:：]?|"
                rf"問題{next_riddle_num}[:：]?)"
            )
            if re.search(extra_pattern, assistant_message.content):
                end_msg = RiddleChatService.RIDDLE_END_MESSAGE
                if end_msg in assistant_message.content:
                    parts = assistant_message.content.split(end_msg)
                    # 余計な出題パターンで分割し、その前の部分（感想）を取得
                    main_content = re.split(extra_pattern, parts[0])[0].strip()
                    # 空行などを整理して再構成
                    assistant_message.content = main_content.rstrip() + "\n\n" + end_msg

            # 評価前に、今回のアシスタントメッセージを履歴に追加して文脈を完璧にする
            chat_service.chat_history.append(assistant_message)

            evaluation_text = chat_service.evaluate(
                login_user=user_message.user, riddle_set=riddle_set
            )
            assistant_message.content += f"\n\n{evaluation_text}"

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
        )
