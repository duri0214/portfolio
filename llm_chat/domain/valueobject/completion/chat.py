import os
from dataclasses import dataclass

from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType, Message
from llm_chat.models import ChatLogs


@dataclass
class MessageDTO:
    """
    GPT APIやデータベース操作に使用されるデータ転送オブジェクト（DTO）。

    Attributes:
        user (User): メッセージを送信するユーザー。
        role (RoleType): メッセージを送信した役割（例: ユーザ、アシスタント、システム）。
        content (str): メッセージの内容。
        file_path (str, optional): 添付ファイルのURLパス。デフォルトは None。
        file_name (str, optional): 添付ファイルの名前。デフォルトは None。
    """

    user: User
    role: RoleType
    content: str
    model_name: str | None = None
    is_riddle: bool = False
    file_path: str | None = None
    file_name: str | None = None

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
            model_name=self.model_name,
            is_riddle=self.is_riddle,
        )
        if self.file_path:
            chat_log.file.name = self.file_path

        return chat_log

    def to_display(self) -> dict:
        """
        このDTOを表示用の辞書に変換します。
        """
        return {
            "role": self.role.name,
            "content": self.content,
            "username": self.user.username,
            "model_name": self.model_name,
            "is_riddle": self.is_riddle,
            "file_url": self.file_path if self.file_path else None,
            "file_name": (
                os.path.basename(self.file_name) if self.file_name else "No File"
            ),
        }
