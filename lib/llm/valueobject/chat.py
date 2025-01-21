import uuid
from dataclasses import dataclass
from enum import Enum


class RoleType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    role: RoleType
    content: str

    def to_dict(self):
        return {"role": self.role.value, "content": self.content}


@dataclass
class MessageChunk:
    messages: list[Message]
    model: str
    max_tokens: int = 1000

    def to_jsonl_entry(self) -> dict:
        """指定されたJSONLの1エントリを生成する"""
        return {
            "custom_id": str(uuid.uuid4()),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": self.model,
                "messages": [message.to_dict() for message in self.messages],
                "max_tokens": self.max_tokens,
            },
        }
