from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.service.common import ChatService
from llm_chat.domain.service.riddle import RIDDLE_END_MESSAGE
from llm_chat.domain.usecase.base import UseCase
from llm_chat.domain.valueobject.chat import MessageDTO, GenderType, Gender


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
            model_name="Riddle",
            is_riddle=True,
        )

        # なぞなぞは明示的に is_riddle=True を指定
        assistant_message = chat_service.generate(
            user_message, is_riddle=True, gender=Gender(GenderType.MAN)
        )

        # なぞなぞの終端処理
        if RIDDLE_END_MESSAGE in assistant_message.content:
            evaluation_text = chat_service.evaluate(login_user=user_message.user)
            assistant_message.content += evaluation_text

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name="Riddle",
            is_riddle=True,
        )
