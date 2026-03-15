import os
from dataclasses import dataclass

from django.contrib.auth.models import User
from lib.llm.valueobject.completion import RoleType, Message
from llm_chat.models import ChatLogs
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


@dataclass
class MessageDTO:
    """
    GPT APIやデータベース操作に使用されるデータ転送オブジェクト（DTO）。

    Attributes:
        user (User): メッセージを送信するユーザー。
        role (RoleType): メッセージを送信した役割（例: ユーザ、アシスタント、システム）。
        content (str): メッセージの内容。
        model_name (str, optional): 使用されたモデル名（例: gpt-4o, gemini-2.0-flash）。デフォルトは None。
        use_case_type (str, optional): 使用されたユースケースタイプ（例: OpenAIGpt, Riddle）。デフォルトは UseCaseType.OPENAI_GPT。
        riddle_state (str, optional): なぞなぞセッションの現在の状態（例: WAIT_ANSWER）。デフォルトは None。
        file_path (str, optional): 添付ファイルのURLパス。デフォルトは None。
        file_name (str, optional): 添付ファイルの名前。デフォルトは None。
    """

    user: User
    role: RoleType
    content: str
    model_name: str | None = None
    use_case_type: str = UseCaseType.OPENAI_GPT
    riddle_state: str | None = None
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
            use_case_type=self.use_case_type,
            riddle_state=self.riddle_state,
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
            "use_case_type": self.use_case_type,
            "riddle_state": self.riddle_state,
            "file_url": self.file_path if self.file_path else None,
            "file_name": (
                os.path.basename(self.file_name) if self.file_name else "No File"
            ),
        }
