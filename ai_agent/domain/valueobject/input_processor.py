from dataclasses import dataclass


@dataclass
class GuardrailResult:
    """ガードレール処理結果"""

    blocked: bool
    message: str
    violation_categories: list[str] = None

    def __post_init__(self):
        if self.violation_categories is None:
            self.violation_categories = []


@dataclass
class InputProcessorConfig:
    """InputProcessor設定"""

    forbidden_words: list[str]
    max_input_length: int
    use_openai_moderation: bool
    strict_mode: bool

    @classmethod
    def from_entity(cls, entity):
        """EntityからInputProcessorConfigを生成"""
        # GuardrailConfigが存在する場合はそこから取得、なければデフォルト値
        try:
            config = entity.guardrailconfig
            return cls(
                forbidden_words=config.forbidden_words,
                max_input_length=config.max_input_length,
                use_openai_moderation=config.use_openai_moderation,
                strict_mode=config.strict_mode,
            )
        except AttributeError:
            # GuardrailConfigが存在しない場合のデフォルト値
            return cls(
                forbidden_words=["abc", "test_forbidden", "禁止ワード"],
                max_input_length=500,
                use_openai_moderation=True,
                strict_mode=entity.thinking_type == "openai_assistant_strict",
            )


@dataclass
class ProcessedInput:
    """処理済み入力"""

    original_input: str
    processed_input: str
    is_blocked: bool
    block_reason: str = ""

    @property
    def should_respond(self) -> bool:
        """応答すべきかどうか"""
        return not self.is_blocked
