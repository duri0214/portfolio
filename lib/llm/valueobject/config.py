from abc import ABC
from dataclasses import dataclass
from typing import Literal


@dataclass
class ApiConfig(ABC):
    api_key: str
    max_tokens: int


OpenAiModel = Literal["gpt-5", "gpt-5-mini", "dall-e-3", "tts-1", "whisper-1"]
GeminiModel = Literal["gemini-2.0-flash", "gemini-2.5-flash"]


@dataclass
class OpenAIGptConfig(ApiConfig):
    model: OpenAiModel


@dataclass
class GeminiConfig(ApiConfig):
    model: GeminiModel
