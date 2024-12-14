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
