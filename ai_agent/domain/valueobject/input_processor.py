from dataclasses import dataclass


@dataclass
class GuardrailResult:
    """
    ガードレール処理結果を表すValue Object

    入力検証やコンテンツフィルタリングの結果を保持する。
    ガードレールによって入力がブロックされた場合の詳細情報を含む。

    Attributes:
        blocked (bool): 入力がブロックされたかどうか
        message (str): ユーザーに表示するメッセージ（ブロック時の理由説明）
        violation_categories (list[str]): 違反カテゴリのリスト
            例: ["forbidden_word", "moderation_error", "length_limit"]

    Examples:
        result = GuardrailResult(
            blocked=True,
            message="禁止ワードが含まれています",
            violation_categories=["forbidden_word"])
        # result.blocked -> True

        safe_result = GuardrailResult(
            blocked=False,
            message="入力は安全です")
        # safe_result.blocked -> False
        # safe_result.violation_categories -> []
    """

    blocked: bool
    message: str
    violation_categories: list[str] = None

    def __post_init__(self):
        """
        初期化後処理

        violation_categoriesがNoneの場合、空のリストで初期化する。
        """
        if self.violation_categories is None:
            self.violation_categories = []


@dataclass
class InputProcessorConfig:
    """
    InputProcessor設定を表すValue Object

    入力処理とガードレール機能の設定を保持する。
    Entityから設定を取得するか、デフォルト値を使用する。

    Attributes:
        forbidden_words (list[str]): 禁止ワードのリスト
            これらの単語が含まれる入力は自動的にブロックされる
        max_input_length (int): 入力テキストの最大文字数
            この値を超える入力は長すぎるとしてブロックされる
        use_openai_moderation (bool): OpenAI Moderation APIを使用するか
            Trueの場合、入力と出力の両方でModerationチェックが実行される
        strict_mode (bool): 厳格モードを使用するか
            Trueの場合、より厳しい基準でコンテンツをフィルタリングする

    Examples:
        config = InputProcessorConfig(
            forbidden_words=["spam", "test"],
            max_input_length=1000,
            use_openai_moderation=True,
            strict_mode=False)
        # config.max_input_length -> 1000
        # config.forbidden_words -> ["spam", "test"]
    """

    forbidden_words: list[str]
    max_input_length: int
    use_openai_moderation: bool
    strict_mode: bool

    @classmethod
    def from_entity(cls, entity):
        """
        EntityからInputProcessorConfigを生成

        EntityのGuardrailConfigから設定を取得する。
        GuardrailConfigが存在しない場合はデフォルト値を使用する。

        Args:
            entity: Entityオブジェクト
                guardrail_config属性を持つ可能性がある

        Returns:
            InputProcessorConfig: 設定済みの設定オブジェクト
        """
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
                strict_mode=False,
            )
