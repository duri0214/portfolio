from abc import ABC
from dataclasses import dataclass
from typing import Literal


@dataclass
class ApiConfig(ABC):
    api_key: str
    max_tokens: int


OpenAiModel = Literal[
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5.6",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-image-1-mini",
    "tts-1",
    "whisper-1",
]
GeminiModel = Literal["gemini-2.0-flash", "gemini-2.5-flash"]
ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
CompletionApi = Literal["chat_completions", "responses"]


@dataclass(frozen=True)
class ModelName:
    """外部LLMプロバイダーが提供するモデル名を一元管理する値オブジェクト。

    Attributes:
        GPT_4O: 既存のGPT-4o。過去ログの識別と個別互換性のために保持する。
        GPT_4O_MINI: 既存のGPT-4o-mini。過去ログと明示指定の互換性のために保持する。
        GPT_5: 既存のGPT-5。過去ログの識別と個別互換性のために保持する。
        GPT_5_MINI: 既存のGPT-5-mini。過去ログの識別と個別互換性のために保持する。
        GPT_5_6: GPT-5.6のエイリアス。Solへルーティングされるため既定値には使用しない。
        GPT_5_6_SOL: GPT-5.6系の品質・推論重視モデル。
        GPT_5_6_TERRA: GPT-5.6系の品質とコストのバランスを取るモデル。
        GPT_5_6_LUNA: GPT-5.6系の低コスト・大量処理向けモデル。
        GPT_IMAGE_1_MINI: 画像生成専用モデル。
        TTS_1: 音声合成専用モデル。
        WHISPER_1: 音声認識専用モデル。
        GEMINI_2_0_FLASH: Gemini 2.0 Flashモデル。
        GEMINI_2_5_FLASH: Gemini 2.5 Flashモデル。
    """

    GPT_4O: OpenAiModel = "gpt-4o"
    GPT_4O_MINI: OpenAiModel = "gpt-4o-mini"
    GPT_5: OpenAiModel = "gpt-5"
    GPT_5_MINI: OpenAiModel = "gpt-5-mini"
    GPT_5_6: OpenAiModel = "gpt-5.6"
    GPT_5_6_SOL: OpenAiModel = "gpt-5.6-sol"
    GPT_5_6_TERRA: OpenAiModel = "gpt-5.6-terra"
    GPT_5_6_LUNA: OpenAiModel = "gpt-5.6-luna"
    GPT_IMAGE_1_MINI: OpenAiModel = "gpt-image-1-mini"
    TTS_1: OpenAiModel = "tts-1"
    WHISPER_1: OpenAiModel = "whisper-1"
    GEMINI_2_0_FLASH: GeminiModel = "gemini-2.0-flash"
    GEMINI_2_5_FLASH: GeminiModel = "gemini-2.5-flash"


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
    """本番のLLM呼び出しごとに選択したGPT-5.6系の既定プロファイル。

    Attributes:
        KOKKAI_SCENARIO: 会議録シナリオの要約・選択肢生成。コスト制約を優先してLunaを使う。
        USA_RESEARCH: MSCIレポート要約。金融文書の読み取りとコストのバランスでTerraを使う。
        LLM_CHAT: 通常チャット。応答品質とコストのバランスでTerraを使う。
        LLM_RIDDLE: なぞなぞ対話。会話品質を優先してTerraを使う。
        LLM_STREAMING: ストリーミングチャット。低遅延を優先してLunaを使う。
        LLM_RAG: PDF RAG回答。検索文脈の整理と品質のバランスでTerraを使う。
        ROKUNOHE_MINUTES_RAG: 六戸町会議録RAG。長文根拠の整理と品質のバランスでTerraを使う。
        SHOPPING_REVIEW: Google Mapsレビュー分析。大量処理のコストを優先してLunaを使う。
        TAXONOMY_CANDIDATE: 分類候補生成。JSON遵守と候補品質のバランスでTerraを使う。
        AI_AGENT: Tool選択を伴うAgent。推論品質を優先してSolを使い、Agents SDKのResponses経路を利用する。
    """

    KOKKAI_SCENARIO = LlmModelProfile(
        model=ModelName.GPT_5_6_LUNA,
        reasoning_effort="low",
    )
    USA_RESEARCH = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    LLM_CHAT = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    LLM_RIDDLE = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    LLM_STREAMING = LlmModelProfile(model=ModelName.GPT_5_6_LUNA)
    LLM_RAG = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    ROKUNOHE_MINUTES_RAG = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    SHOPPING_REVIEW = LlmModelProfile(model=ModelName.GPT_5_6_LUNA)
    TAXONOMY_CANDIDATE = LlmModelProfile(model=ModelName.GPT_5_6_TERRA)
    AI_AGENT = LlmModelProfile(
        model=ModelName.GPT_5_6_SOL,
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
