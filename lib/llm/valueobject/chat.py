from dataclasses import dataclass
from enum import Enum


class RoleType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """
    単一のチャットメッセージを表すデータクラス。

    Attributes:
        role (RoleType): メッセージを送信した役割（ユーザ、アシスタント、システム）。
        content (str): メッセージ内容。
    """

    role: RoleType
    content: str

    def to_dict(self):
        return {"role": self.role.value, "content": self.content}
