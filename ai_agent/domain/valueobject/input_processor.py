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

        Note:
            strict_modeはentity.thinking_typeが"openai_assistant_strict"の場合にTrueになる
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
                strict_mode=entity.thinking_type == "openai_assistant_strict",
            )


@dataclass
class ProcessedInput:
    """
    処理済み入力を表すValue Object

    ユーザーの入力テキストの処理結果を保持する。
    元の入力、処理済み入力、ブロック状態、ブロック理由を含む。

    Attributes:
        original_input (str): 元のユーザー入力テキスト
        processed_input (str): 正規化・前処理された入力テキスト
        is_blocked (bool): 入力がガードレールによってブロックされたか
        block_reason (str): ブロックされた理由（ユーザー向けメッセージ）

    Examples:
        processed = ProcessedInput(
            original_input="こんにちは",
            processed_input="こんにちは",
            is_blocked=False)
        # processed.should_respond -> True

        blocked_input = ProcessedInput(
            original_input="禁止ワード",
            processed_input="禁止ワード",
            is_blocked=True,
            block_reason="禁止ワードが含まれています")
        # blocked_input.should_respond -> False
    """

    original_input: str
    processed_input: str
    is_blocked: bool
    block_reason: str = ""

    @property
    def should_respond(self) -> bool:
        """
        応答すべきかどうかを判定

        入力がブロックされていない場合にTrueを返す。

        Returns:
            bool: ブロックされていない場合はTrue、ブロックされている場合はFalse
        """
        return not self.is_blocked


@dataclass
class AgentInvoker:
    """
    OpenAI Agents SDKの呼び出し処理を担当するValue Object

    OpenAI Agents SDKのAgentオブジェクトを適切に呼び出し、
    レスポンスを処理してエラーハンドリングを行う。

    Attributes:
        agent (object): OpenAI Agents SDKのAgentインスタンス
        entity_name (str): エンティティ名（エラーメッセージ用）

    Examples:
        invoker = AgentInvoker(agent=my_agent, entity_name="ChatBot")
        # invoker.entity_name -> "ChatBot"

        response = await invoker.execute("Hello, world!")
        # response -> "Hello! How can I help you today?"
    """

    agent: object
    entity_name: str

    async def execute(self, user_input: str) -> str:
        """
        適切なメソッドを選択してAgentを実行

        利用可能なメソッドを自動検出し、Agentを実行する。
        エラーが発生した場合は適切なエラーメッセージを返す。

        Args:
            user_input (str): ユーザーからの入力テキスト

        Returns:
            str: Agentからの応答テキスト、またはエラーメッセージ
        """
        try:
            result = await self._invoke_agent(user_input)
            return self._extract_content(result)
        except Exception as e:
            return self._handle_error(e)

    async def _invoke_agent(self, user_input: str):
        """
        利用可能なメソッドを使用してAgentを実行

        Agent オブジェクトが持つメソッドを優先順位順に検査し、
        利用可能な最初のメソッドを使用してAgentを実行する。

        Args:
            user_input (str): ユーザーからの入力テキスト

        Returns:
            object: Agentからの応答オブジェクト

        Raises:
            AttributeError: 利用可能なメソッドが見つからない場合
        """
        if hasattr(self.agent, "chat"):
            return await self.agent.chat(user_input)
        elif hasattr(self.agent, "run"):
            return await self.agent.run(user_input)
        else:
            raise AttributeError(f"Agent has no callable method for processing input")

    @staticmethod
    def _extract_content(result) -> str:
        """
        結果からコンテンツを抽出

        Agentの応答オブジェクトから実際のテキストコンテンツを抽出する。
        content属性がある場合はそれを使用し、なければ文字列に変換する。

        Args:
            result (object): Agentからの応答オブジェクト

        Returns:
            str: 抽出されたコンテンツテキスト
        """
        return result.content if hasattr(result, "content") else str(result)

    def _handle_error(self, error: Exception) -> str:
        """
        エラーハンドリング

        Agent実行中に発生したエラーをログに記録し、
        ユーザーに適切なエラーメッセージを返す。

        Args:
            error (Exception): 発生したエラー

        Returns:
            str: ユーザー向けのエラーメッセージ
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Agents SDK error for entity {self.entity_name}: {error}")
        return f"{self.entity_name}: 申し訳ありませんが、現在応答できません。しばらくしてから再度お試しください。"
