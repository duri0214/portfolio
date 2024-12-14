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
        このDTOをデータベース格納用のChatLogsWithLineエンティティに変換します。
        """
        return ChatLogs(
            user=self.user,
            role=self.role.value,
            content=self.content,
            file_path=self.file_path,
            invisible=self.invisible,
        )


class GenderType(Enum):
    MAN = "man"
    WOMAN = "woman"


@dataclass
class Gender:
    gender: GenderType

    @property
    def name(self) -> str:
        return "男性" if self.gender == GenderType.MAN else "女性"
