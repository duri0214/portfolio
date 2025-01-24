import uuid
from dataclasses import dataclass

from lib.llm.valueobject.chat import Message


@dataclass
class MessageChunk:
    """
    チャットメッセージの塊を表現するデータクラス。
    API呼び出し時に使用される構造。

    Attributes:
        messages (list[Message]): メッセージのリスト。
        model (str): 使用するモデルの名前。
        max_tokens (int): 最大トークン数（デフォルトは1000）。
    """

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
