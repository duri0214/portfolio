import html
import os

from agents import Agent
from agents.guardrail import InputGuardrail, OutputGuardrail, GuardrailFunctionOutput

from ai_agent.domain.valueobject.input_processor import (
    GuardrailResult,
    InputProcessorConfig,
)
from lib.llm.service.guardrail import ModerationService
from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.config import OpenAIGptConfig
from lib.llm.valueobject.guardrail import GuardRailSignal


class InputProcessor:
    """
    OpenAI Agent用の入力処理サービス
    ガードレール機能を含む安全な入力処理を提供
    """

    def __init__(self, entity):
        self.entity = entity
        self.config = InputProcessorConfig.from_entity(entity)
        self.moderation_service = ModerationService()

        # LlmCompletionServiceの初期化
        self.llm_config = OpenAIGptConfig(
            model="gpt-5-mini",
            max_tokens=2000,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        self.llm_service = LlmCompletionService(self.llm_config)

        # Agents SDKの初期化
        self._setup_openai_agents()

    def _setup_openai_agents(self):
        """
        OpenAI Agents SDKの初期化とガードレール設定

        エージェントの作成と入力・出力ガードレールの設定を行う。
        エンティティの設定に基づいて適切なガードレールを組み合わせ、
        安全で信頼性の高い対話システムを構築する。

        処理内容:
        1. Agentオブジェクトの作成（gpt-4o-mini使用）
        2. 入力ガードレールの設定
           - OpenAI Moderation（設定により有効化）
           - カスタムガードレール（必須）
        3. 出力ガードレールの設定
           - OpenAI Moderation（設定により有効化）

        Note:
            - エージェントの指示は日本語での親しみやすい対話を重視
            - カスタムガードレールは常に有効（禁止ワード、文字数制限等）
            - OpenAI Moderationは設定により選択的に有効化
        """
        # エージェントの作成
        self.agent: Agent = Agent(
            name=self.entity.name,
            model="gpt-4o-mini",
            instructions=f"""あなたは{self.entity.name}です。
                井戸端会議のように気楽に話してください。
                不適切な内容には応答しないでください。
                日本語で回答してください。

                会話の文脈を理解して、自然で興味深い返答をしてください。
                他の参加者との会話の流れに合わせて、適切なタイミングで発言してください。""",
        )

        # 入力ガードレール設定
        self.input_guardrails: list[InputGuardrail] = []
        if self.config.use_openai_moderation:
            self.input_guardrails.append(self._create_input_guardrail())

        self.input_guardrails.append(self._create_custom_guardrail())

        # 出力ガードレール設定
        self.output_guardrails = []
        if self.config.use_openai_moderation:
            self.output_guardrails.append(self._create_output_guardrail())

        # ガードレールをエージェントに適用
        try:
            for guardrail in self.input_guardrails:
                self.agent.input_guardrails.append(guardrail)

            for guardrail in self.output_guardrails:
                self.agent.output_guardrails.append(guardrail)
        except Exception as e:
            print(f"ガードレール設定中にエラーが発生: {e}")

        print(f"OpenAI Agent初期化完了: {self.entity.name}")

    def _create_input_guardrail(self):
        """
        OpenAI Moderation APIを使用した入力ガードレールを作成

        ModerationServiceを使用してユーザー入力を事前チェックするガードレールを作成する。
        不適切なコンテンツ（暴力、ハラスメント、自傷行為など）を検出し、
        設定に応じて厳格モードまたは標準モードで判定を行う。

        Returns:
            InputGuardrail: OpenAI Moderation APIベースのガードレールオブジェクト

        Note:
            - ModerationService.create_guardrailの詳細処理を参照
            - strict_modeがTrueの場合、より厳格な基準で判定
            - エンティティ名を含むパーソナライズされたエラーメッセージを生成
        """
        moderation_check = self.moderation_service.create_guardrail(
            self.entity.name, self.config.strict_mode
        )

        return InputGuardrail(
            name="moderation_guardrail", guardrail_function=moderation_check
        )

    def _create_custom_guardrail(self):
        """
        カスタムガードレールを作成

        禁止ワード、文字数制限、空文字チェックを行うガードレール関数を作成する。
        入力テキストの型に応じた前処理を行い、複数の検証ルールを適用する。

        Returns:
            InputGuardrail: カスタムガードレールオブジェクト

        Note:
            内部のcustom_check関数は以下の処理を順次実行:
            1. input_textの型チェック（str, list, その他）
            2. 統一された文字列形式（processed_text）への変換
            3. 禁止ワードチェック（大文字小文字無視）
            4. 文字数制限チェック
            5. 空文字・空白文字チェック
        """

        def custom_check(_, __, input_text):
            if isinstance(input_text, str):
                processed_text = input_text
            elif isinstance(input_text, list):
                processed_text = str(input_text[0]) if input_text else ""
            else:
                processed_text = str(input_text)

            for word in self.config.forbidden_words:
                if word.lower() in processed_text.lower():
                    return GuardrailFunctionOutput(
                        output_info=f"{self.entity.name}: 申し訳ありませんが、その内容にはお答えできません。",
                        tripwire_triggered=True,
                    )

            if len(processed_text) > self.config.max_input_length:
                return GuardrailFunctionOutput(
                    output_info=f"{self.entity.name}: メッセージが長すぎます。{self.config.max_input_length}文字以内でお願いします。",
                    tripwire_triggered=True,
                )

            if not processed_text.strip():
                return GuardrailFunctionOutput(
                    output_info=f"{self.entity.name}: メッセージが空です。何かお聞きしたいことがあれば教えてください。",
                    tripwire_triggered=True,
                )

            return GuardrailFunctionOutput(output_info="", tripwire_triggered=False)

        return InputGuardrail(name="custom_guardrail", guardrail_function=custom_check)

    def _create_output_guardrail(self):
        """
        OpenAI Moderation APIを使用した出力ガードレールを作成

        ModerationServiceを使用してGPT応答を事後チェックするガードレールを作成する。
        生成されたテキストが不適切なコンテンツを含んでいないかを検証し、
        問題がある場合は安全な代替メッセージに置き換える。

        Returns:
            OutputGuardrail: OpenAI Moderation APIベースの出力ガードレールオブジェクト

        Note:
            - ModerationService.create_output_moderation_guardrailの詳細処理を参照
            - エージェントが生成したテキストの最終段階でのセーフティチェック
            - ユーザーに不適切な内容が表示されることを防止
        """
        output_moderation_check = (
            self.moderation_service.create_output_moderation_guardrail(self.entity.name)
        )

        return OutputGuardrail(
            name="output_moderation_guardrail",
            guardrail_function=output_moderation_check,
        )

    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        入力テキストからHTMLタグなどの危険な要素を除去

        Args:
            text (str): 無害化する入力テキスト

        Returns:
            str: 無害化されたテキスト
        """
        # HTMLタグの無害化（タグをエスケープしてテキストとして表示）
        sanitized = html.escape(text)
        return sanitized

    def process_input(self, user_input: str) -> str:
        """
        ユーザー入力を処理してエージェントの応答を生成

        ガードレールを使用して入力を検証し、
        安全であれば処理を行い、そうでなければブロックメッセージを返す。

        Args:
            user_input (str): ユーザーからの入力テキスト

        Returns:
            str: エージェントからの応答テキスト

        Note:
            処理フロー:
            1. ガードレール検証を実行
            2. 安全な入力であれば_process_defaultで処理
            3. 不適切な入力であればブロックメッセージを返す
        """
        try:
            # 入力の無害化
            sanitized_input = self.sanitize_input(user_input)

            # ガードレール機能による入力検証
            validation_result = self._check_guardrails(user_input)

            # ガードレールをパスした場合、処理を実行
            if not validation_result.blocked:
                return self._process_default(sanitized_input)

            # ブロックされた場合はブロックメッセージを返す
            return (
                validation_result.message
                or f"{self.entity.name}: その入力は許可されていません。"
            )
        except Exception as e:
            print(f"Input processing error: {e}")
            return f"{self.entity.name}: 処理中にエラーが発生しました。しばらくしてからお試しください。"

    def _check_guardrails(self, user_input: str) -> GuardrailResult:
        """
        ガードレール機能による入力チェック

        Args:
            user_input: チェック対象の入力テキスト

        Returns:
            ガードレール処理結果
        """
        # 1. 静的ガードレール（事前定義ルール）
        static_result = self._static_guardrails(user_input)
        if static_result.blocked:
            return static_result

        # 2. 動的ガードレール（OpenAI Moderation）
        if self.config.use_openai_moderation:
            dynamic_result = self._dynamic_guardrails(user_input)
            if dynamic_result.blocked:
                return dynamic_result

        return GuardrailResult(blocked=False, message="")

    def _static_guardrails(self, user_input: str) -> GuardrailResult:
        """
        静的ガードレール：事前定義されたルールによるチェック

        Args:
            user_input: チェック対象の入力テキスト

        Returns:
            静的ガードレール処理結果
        """
        # 禁止ワードチェック
        for word in self.config.forbidden_words:
            if word.lower() in user_input.lower():
                return GuardrailResult(
                    blocked=True,
                    message=f"{self.entity.name}: 申し訳ありませんが、その内容にはお答えできません。",
                    violation_categories=["forbidden_word"],
                )

        # 文字数制限チェック
        if len(user_input) > self.config.max_input_length:
            return GuardrailResult(
                blocked=True,
                message=f"{self.entity.name}: メッセージが長すぎます。{self.config.max_input_length}文字以内でお願いします。",
                violation_categories=["length_limit"],
            )

        # 空文字チェック
        if not user_input.strip():
            return GuardrailResult(
                blocked=True,
                message=f"{self.entity.name}: メッセージが空です。何かお聞きしたいことがあれば教えてください。",
                violation_categories=["empty_input"],
            )

        return GuardrailResult(blocked=False, message="")

    def _dynamic_guardrails(self, user_input: str) -> GuardrailResult:
        """
        動的ガードレール：OpenAI Moderationによるリアルタイム判定

        Args:
            user_input: チェック対象の入力テキスト

        Returns:
            動的ガードレール処理結果
        """
        moderation_result = self.moderation_service.check_input_moderation(
            user_input, self.entity.name, self.config.strict_mode
        )

        if moderation_result.signal == GuardRailSignal.RED:
            return GuardrailResult(
                blocked=True,
                message=moderation_result.detail
                or f"{self.entity.name}: その内容は適切ではないため、お答えできません。",
                violation_categories=(
                    [moderation_result.reason] if moderation_result.reason else []
                ),
            )

        return GuardrailResult(blocked=False, message="")

    def _process_default(self, user_input: str) -> str:
        """
        オウム返し応答生成

        Args:
            user_input: 処理済み入力テキスト（既に無害化済み）

        Returns:
            エンティティ名付きのオウム返しテキスト
        """
        return f"{self.entity.name}: {user_input}"
