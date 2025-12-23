import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Any


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


@dataclass
class RagDocument:
    """
    RAGの検索結果ドキュメントを保持するVO。
    """

    page_content: str
    metadata: dict[str, Any]


@dataclass
class RagResponse:
    """
    RAGの回答結果を保持するVO。
    """

    answer: str
    sources: str
    source_documents: list[RagDocument]
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "source_documents": self.source_documents,
            "warning": self.warning,
        }

    def __getitem__(self, key):
        return getattr(self, key)


FinishReason = Literal[
    "stop", "length", "tool_calls", "content_filter", "function_call"
]


@dataclass
class StreamResponse:
    """ストリームで返すレスポンスをラップするVO"""

    content: str | None  # delta.content
    finish_reason: FinishReason | None  # 終了理由 (e.g., stop, length, etc.)

    def to_json(self) -> str:
        serialized_data = {
            "content": self.content,
            "finish_reason": self.finish_reason,
        }
        return json.dumps(serialized_data)
