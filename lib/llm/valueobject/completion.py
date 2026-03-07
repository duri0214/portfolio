import json
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Any

from pydantic import BaseModel, Field


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
        content (str): メッセージの内容。
    """

    role: RoleType
    content: str

    def to_dict(self):
        return {"role": self.role.value, "content": self.content}


class RagDocument(BaseModel):
    """
    RAGの検索結果ドキュメントを保持するVO。

    Attributes:
        page_content (str): 抽出されたドキュメントの本文。
        metadata (dict[str, Any]): ドキュメントの出典情報（source, fileなど）。
    """

    page_content: str
    metadata: dict[str, Any]


class ChatResult(BaseModel):
    """
    LLMからの構造化されたレスポンスを格納する共通のデータ構造。

    Attributes:
        answer (str): LLMの回答メインコンテンツ。
        explanation (str | None): 回答の根拠や補足説明。
        metadata (dict[str, Any]): トークン数、モデル名、ステータスなどの付随情報。
    """

    answer: str = Field(..., description="LLMの回答メインコンテンツ")
    explanation: str | None = Field(None, description="回答の根拠・解説")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="トークン数やステータスなどの付随情報"
    )


class RagResponse(ChatResult):
    """
    RAGの回答結果を保持するVO。

    Attributes:
        answer (str): 生成された回答。
        sources (str): 出典情報（人間可読な形式）。
        source_documents (list[RagDocument]): 検索によって取得されたソースドキュメントのリスト。
        warning (str | None): 文字数超過などの警告メッセージ。
    """

    sources: str = Field(..., description="回答のソース情報")
    source_documents: list[RagDocument] = Field(
        ..., description="参照したドキュメントのリスト"
    )
    warning: str | None = Field(None, description="警告メッセージ")

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
    """
    ストリームで返すレスポンスをラップするVO。

    Attributes:
        content (str | None): 逐次生成される回答の一部（delta.content）。
        finish_reason (FinishReason | None): 終了理由（stop, lengthなど）。
    """

    content: str | None  # delta.content
    finish_reason: FinishReason | None  # 終了理由 (e.g., stop, length, etc.)

    def to_json(self) -> str:
        serialized_data = {
            "content": self.content,
            "finish_reason": self.finish_reason,
        }
        return json.dumps(serialized_data)
