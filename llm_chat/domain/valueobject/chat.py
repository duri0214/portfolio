from dataclasses import dataclass
from enum import Enum

from django.contrib.auth.models import User

from lib.llm.valueobject.chat import RoleType, Message
from llm_chat.models import ChatLogsWithLine


@dataclass
class MessageDTO:
    user: User
    role: RoleType
    content: str
    invisible: bool
    file_path: str = None

    def to_request(self) -> Message:
        """
        このDTOをGPT APIへのリクエストとして適切なMessageオブジェクトに変換します。
        """
        return Message(role=self.role, content=self.content)

    def to_entity(self) -> ChatLogsWithLine:
        """
        このDTOをデータベース格納用のChatLogsWithLineエンティティに変換します。
        """
        return ChatLogsWithLine(
            user=self.user,
            role=self.role.value,
            content=self.content,
            file_path=self.file_path,
            invisible=self.invisible,
        )

    def __str__(self):
        return (
            f"user_id: {self.user.pk}, "
            f"role: {self.role}, "
            f"content: {self.content}, "
            f"invisible: {self.invisible}, "
            f"file_path: {self.file_path}"
        )


class Gender:
    def __init__(self, gender):
        if gender not in {"man", "woman"}:
            raise ValueError("Invalid gender")
        self.gender = gender

    @property
    def name(self) -> str:
        return "男性" if self.gender == "man" else "女性"
