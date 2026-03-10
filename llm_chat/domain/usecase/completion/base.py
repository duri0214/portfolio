from abc import ABC, abstractmethod
from typing import Generator

from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType, StreamResponse
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.valueobject.completion.message import MessageDTO


class UseCase(ABC):
    def __init__(self):
        self.repository = ChatLogRepository()

    @abstractmethod
    def execute(
        self, user: User, content: str | None
    ) -> MessageDTO | Generator[StreamResponse, None, None]:
        pass

    def _insert_assistant_message(
        self,
        user: User,
        content: str,
        model_name: str,
        is_riddle: bool = False,
        file_path: str | None = None,
    ) -> MessageDTO:
        assistant_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            model_name=model_name,
            is_riddle=is_riddle,
            file_path=file_path,
        )
        self.repository.insert(assistant_message)
        return assistant_message
