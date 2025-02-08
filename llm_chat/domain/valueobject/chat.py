from dataclasses import dataclass
from enum import Enum

from django.contrib.auth.models import User

from lib.llm.valueobject.chat import RoleType, Message
from llm_chat.models import ChatLogs


@dataclass
class MessageDTO:
    """
    GPT APIやデータベース操作に使用されるデータ転送オブジェクト（DTO）。

    Attributes:
        user (User): メッセージを送信するユーザー。
        role (RoleType): メッセージを送信した役割（例: ユーザ、アシスタント、システム）。
        content (str): メッセージの内容。
        invisible (bool): メッセージがユーザーに非表示であるかどうかを示すフラグ。
        file_path (str, optional): 添付ファイルのパス。デフォルトは None。
    """

    user: User
    role: RoleType
    content: str
    invisible: bool
    file_path: str = None

    def to_message(self) -> Message:
        """
        このDTOをGPT APIへのリクエストとして適切なMessageオブジェクトに変換します。
        """
        return Message(role=self.role, content=self.content)

    def to_entity(self) -> ChatLogs:
        """
        このDTOをデータベース格納用のChatLogsエンティティに変換します。
        """
        chat_log = ChatLogs(
            user=self.user,
            role=self.role.value,
            content=self.content,
            invisible=self.invisible,
        )
        if self.file_path:
            chat_log.file.name = self.file_path

        return chat_log

    def to_dict(self):
        return {
            "user": self.user.username,
            "role": self.role.name,
            "content": self.content,
            "file_path": self.file_path,
            "invisible": self.invisible,
        }


class GenderType(Enum):
    MAN = "man"
    WOMAN = "woman"


@dataclass
class Gender:
    gender: GenderType

    @property
    def name(self) -> str:
        return "男性" if self.gender == GenderType.MAN else "女性"
