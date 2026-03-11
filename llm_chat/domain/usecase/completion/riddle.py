from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.usecase.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import GenderType, Gender
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RiddleUseCase(UseCase):
    """なぞなぞユースケース"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config

    def execute(self, user: User, content: str | None) -> MessageDTO:
        if content is None:
            raise ValueError("content cannot be None for RiddleUseCase")

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
            user_message, use_case_type="Riddle", gender=Gender(GenderType.MAN)
        )

        # なぞなぞの終端処理
        if RiddleChatService.RIDDLE_END_MESSAGE in assistant_message.content:
            evaluation_text = chat_service.evaluate(login_user=user_message.user)
            assistant_message.content += evaluation_text

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=self.config.model,
            use_case_type=UseCaseType.RIDDLE,
        )
