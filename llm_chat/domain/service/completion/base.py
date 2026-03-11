from abc import ABC, abstractmethod

from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAiModel, GeminiModel
from llm_chat.domain.valueobject.completion.chat import MessageDTO


class BaseChatService(ABC):
    def __init__(self, model_name: OpenAiModel | GeminiModel | None = None):
        self.model_name = model_name

    @abstractmethod
    def generate(self, **kwargs):
        pass

    def _create_assistant_message(
        self,
        user: User,
        content: str,
        use_case_type: str = "OpenAIGpt",
        file_path: str | None = None,
    ) -> MessageDTO:
        return MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            model_name=self.model_name,
            use_case_type=use_case_type,
            file_path=file_path,
        )
