from abc import ABC
from dataclasses import dataclass
from typing import Literal


@dataclass
class ApiConfig(ABC):
    api_key: str
    max_tokens: int


OpenAiModel = Literal[
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-image-1-mini",
    "tts-1",
    "whisper-1",
]
GeminiModel = Literal["gemini-2.0-flash", "gemini-2.5-flash"]
EmbeddingModel = Literal["text-embedding-3-small"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
CompletionApi = Literal["chat_completions", "responses"]


@dataclass(frozen=True)
class ModelName:
    """外部LLMプロバイダーが提供するモデル名を一元管理する値オブジェクト。

    現在利用するモデルと、画像・音声・Embeddingなどの専用モデルを定義する。
    """

    GPT_5_6_SOL: OpenAiModel = "gpt-5.6-sol"
    GPT_5_6_TERRA: OpenAiModel = "gpt-5.6-terra"
    GPT_5_6_LUNA: OpenAiModel = "gpt-5.6-luna"
    GPT_IMAGE_1_MINI: OpenAiModel = "gpt-image-1-mini"
    TTS_1: OpenAiModel = "tts-1"
    WHISPER_1: OpenAiModel = "whisper-1"
    GEMINI_2_0_FLASH: GeminiModel = "gemini-2.0-flash"
    GEMINI_2_5_FLASH: GeminiModel = "gemini-2.5-flash"
    TEXT_EMBEDDING_3_SMALL: EmbeddingModel = "text-embedding-3-small"


@dataclass(frozen=True)
class LlmModelProfile:
    """用途別に採用するLLMとAPI互換性を表す不変設定。

    Attributes:
        model: 呼び出しに使用するモデル名。
        api: 実装が利用するAPI種別。現在の共通テキストサービスはChat Completionsを利用する。
        reasoning_effort: 推論モデルへ渡す推論量。未指定の場合はAPIの既定値を利用する。
        supports_structured_outputs: structured outputsを利用できるモデルかどうか。
    """

    model: OpenAiModel
    api: CompletionApi = "chat_completions"
    reasoning_effort: ReasoningEffort | None = None
    supports_structured_outputs: bool = True


class ModelDefaults:
    """本番のテキスト生成を統一するGPT-5.6 Lunaの既定プロファイル。

    Attributes:
        TEXT_MODEL: Portfolioで利用するテキスト生成モデル。全用途でLunaへ統一する。
        KOKKAI_SCENARIO: 会議録シナリオの要約・選択肢生成。JSON出力のため推論量をlowにする。
        USA_RESEARCH: MSCIレポート要約。共通テキストモデルを利用する。
        LLM_CHAT: 通常チャット。共通テキストモデルを利用する。
        LLM_RIDDLE: なぞなぞ対話。共通テキストモデルを利用する。
        LLM_STREAMING: ストリーミングチャット。共通テキストモデルを利用する。
        LLM_RAG: PDF RAG回答。共通テキストモデルを利用する。
        ROKUNOHE_MINUTES_RAG: 六戸町会議録RAG。共通テキストモデルを利用する。
        SHOPPING_REVIEW: Google Mapsレビュー分析。共通テキストモデルを利用する。
        TAXONOMY_CANDIDATE: 分類候補生成。共通テキストモデルを利用する。
        AI_AGENT: Tool選択を伴うAgent。共通テキストモデルをResponses経路で利用する。
    """

    TEXT_MODEL: OpenAiModel = ModelName.GPT_5_6_LUNA
    KOKKAI_SCENARIO = LlmModelProfile(
        model=TEXT_MODEL,
        reasoning_effort="low",
    )
    USA_RESEARCH = LlmModelProfile(model=TEXT_MODEL)
    LLM_CHAT = LlmModelProfile(model=TEXT_MODEL)
    LLM_RIDDLE = LlmModelProfile(model=TEXT_MODEL)
    LLM_STREAMING = LlmModelProfile(model=TEXT_MODEL)
    LLM_RAG = LlmModelProfile(model=TEXT_MODEL)
    ROKUNOHE_MINUTES_RAG = LlmModelProfile(model=TEXT_MODEL)
    SHOPPING_REVIEW = LlmModelProfile(model=TEXT_MODEL)
    TAXONOMY_CANDIDATE = LlmModelProfile(model=TEXT_MODEL)
    AI_AGENT = LlmModelProfile(
        model=TEXT_MODEL,
        api="responses",
        reasoning_effort="low",
    )


@dataclass
class OpenAIGptConfig(ApiConfig):
    """Chat Completions経由のOpenAIテキスト生成設定。

    Attributes:
        api_key: OpenAI APIへ接続するためのAPIキー。
        max_tokens: 応答に許可する最大トークン数。
        model: 呼び出しに使用するOpenAIモデル名。
        reasoning_effort: GPT-5.6系へ渡す推論量。未指定の場合は送信しない。
    """

    model: OpenAiModel
    reasoning_effort: ReasoningEffort | None = None

    @classmethod
    def from_profile(
        cls,
        profile: LlmModelProfile,
        *,
        api_key: str,
        max_tokens: int,
    ) -> "OpenAIGptConfig":
        """Chat Completions用プロファイルからAPI設定を生成します。

        Args:
            profile: 利用するOpenAIモデルの共通プロファイル。
            api_key: OpenAI APIキー。
            max_tokens: 応答に許可する最大トークン数。

        Returns:
            OpenAIGptConfig: プロファイルとAPI接続情報を結合した設定。

        Raises:
            ValueError: Responses API用プロファイルを指定した場合。
        """
        if profile.api != "chat_completions":
            raise ValueError(
                "OpenAIGptConfig.from_profile requires a Chat Completions profile."
            )
        return cls(
            api_key=api_key,
            max_tokens=max_tokens,
            model=profile.model,
            reasoning_effort=profile.reasoning_effort,
        )


@dataclass
class GeminiConfig(ApiConfig):
    model: GeminiModel
