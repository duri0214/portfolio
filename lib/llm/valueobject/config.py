from abc import ABC
from dataclasses import dataclass, field
from typing import Literal


def validate_temperature(value: float) -> float:
    if not 0 <= value <= 1:
        raise ValueError("Temperature should be a float value between 0 and 1.")
    return value


@dataclass
class ApiConfig(ABC):
    api_key: str
    temperature: float = field(metadata={"validate": validate_temperature})
    max_tokens: int


OpenAiModel = Literal["gpt-4o", "gpt-4o-mini"]
GeminiModel = Literal["gemini-1.5-flash"]


@dataclass
class OpenAIGptConfig(ApiConfig):
    model: OpenAiModel


@dataclass
class GeminiConfig(ApiConfig):
    model: GeminiModel
