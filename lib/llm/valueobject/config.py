from abc import ABC
from dataclasses import dataclass
from typing import Literal


@dataclass
class ApiConfig(ABC):
    api_key: str
    max_tokens: int


OpenAiModel = Literal[
    "gpt-4o", "gpt-5", "gpt-5-mini", "gpt-image-1-mini", "tts-1", "whisper-1"
]
GeminiModel = Literal["gemini-2.0-flash", "gemini-2.5-flash"]


@dataclass(frozen=True)
class ModelName:
    GPT_4O: OpenAiModel = "gpt-4o"
    GPT_5: OpenAiModel = "gpt-5"
    GPT_5_MINI: OpenAiModel = "gpt-5-mini"
    GPT_IMAGE_1_MINI: OpenAiModel = "gpt-image-1-mini"
    TTS_1: OpenAiModel = "tts-1"
    WHISPER_1: OpenAiModel = "whisper-1"
    GEMINI_2_0_FLASH: GeminiModel = "gemini-2.0-flash"
    GEMINI_2_5_FLASH: GeminiModel = "gemini-2.5-flash"


@dataclass
class OpenAIGptConfig(ApiConfig):
    model: OpenAiModel


@dataclass
class GeminiConfig(ApiConfig):
    model: GeminiModel
