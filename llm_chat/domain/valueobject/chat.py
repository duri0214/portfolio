from dataclasses import dataclass
from enum import Enum

from django.contrib.auth.models import User

from lib.llm.valueobject.chat import RoleType, Message
from llm_chat.models import ChatLogs


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

    def to_entity(self) -> ChatLogs:
        """
        このDTOをデータベース格納用のChatLogsエンティティに変換します。
        """
        chatlog = ChatLogs(
            user=self.user,
            role=self.role.value,
            content=self.content,
            invisible=self.invisible,
        )
        if self.file_path:
            chatlog.file.name = self.file_path

        return chatlog


class GenderType(Enum):
    MAN = "man"
    WOMAN = "woman"


@dataclass
class Gender:
    gender: GenderType

    @property
    def name(self) -> str:
        return "男性" if self.gender == GenderType.MAN else "女性"
