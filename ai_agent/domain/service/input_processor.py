import asyncio
import logging
import os

from agents import Agent
from agents.guardrail import InputGuardrail, OutputGuardrail, GuardrailFunctionOutput

from ai_agent.domain.valueobject.input_processor import (
    AgentInvoker,
    GuardrailResult,
    InputProcessorConfig,
    ProcessedInput,
)
from lib.llm.service.agent import ModerationService
from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig

logger = logging.getLogger(__name__)


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
            model="gpt-4o-mini",
            temperature=0.7,
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
        self.agent = Agent(
            name=self.entity.name,
            model="gpt-4o-mini",
            instructions=f"""あなたは{self.entity.name}です。
                井戸端会議のように気楽に話してください。
                不適切な内容には応答しないでください。
                日本語で回答してください。""",
        )

        # 入力ガードレール設定
        self.input_guardrails = []
        if self.config.use_openai_moderation:
            self.input_guardrails.append(self._create_moderation_guardrail())

        self.input_guardrails.append(self._create_custom_guardrail())

        # 出力ガードレール設定
        self.output_guardrails = []
        if self.config.use_openai_moderation:
            self.output_guardrails.append(self._create_output_moderation_guardrail())

    def _create_moderation_guardrail(self):
        """
        OpenAI Moderation APIを使用した入力ガードレールを作成

        ModerationServiceを使用してユーザー入力を事前チェックするガードレールを作成する。
        不適切なコンテンツ（暴力、ハラスメント、自傷行為など）を検出し、
        設定に応じて厳格モードまたは標準モードで判定を行う。

        Returns:
            InputGuardrail: OpenAI Moderation APIベースのガードレールオブジェクト

        Note:
            - ModerationService.create_moderation_guardrailの詳細処理を参照
            - strict_modeがTrueの場合、より厳格な基準で判定
            - エンティティ名を含むパーソナライズされたエラーメッセージを生成
        """
        moderation_check = self.moderation_service.create_moderation_guardrail(
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

    def _create_output_moderation_guardrail(self):
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

    def process_input(self, user_input: str) -> str:
        """
        ユーザー入力を処理してエージェントの応答を生成

        エンティティのthinking_typeに基づいて適切な処理方法を選択し、
        同期的なインターフェースで応答を返す。OpenAI Agents SDKを使用する場合は
        内部で非同期処理を実行する。

        Args:
            user_input (str): ユーザーからの入力テキスト

        Returns:
            str: エージェントからの応答テキスト

        Note:
            thinking_typeによる処理分岐:
            - "openai_assistant" / "openai_assistant_strict":
              OpenAI Agents SDKを使用（非同期処理）
            - その他: 従来の処理（同期処理）

            非同期処理の同期化について:
            - OpenAI Agents SDKは非同期APIを提供
            - このメソッドは同期的なインターフェースを維持する必要がある
            - asyncio.run()を使用して非同期処理を同期的に実行
            - asyncio.run()は新しいイベントループを作成し、非同期処理を完了まで待機

            処理フロー（OpenAI Agents SDK使用時）:
            1. _process_with_openai_agents()を非同期で実行
            2. asyncio.run()が新しいイベントループを作成
            3. 非同期処理が完了するまでブロック
            4. 結果を同期的に返却
        """
        # thinking_typeに基づく処理の分岐
        if self.entity.thinking_type in ["openai_assistant", "openai_assistant_strict"]:
            return asyncio.run(self._process_with_openai_agents(user_input))
        else:
            # 従来の処理（ガードレールチェック付き）
            processed = self._preprocess_input(user_input)
            if not processed.should_respond:
                return processed.block_reason
            return self._process_default(processed.processed_input)

    async def _process_with_openai_agents(self, user_input: str) -> str:
        """
        Agents SDKを使用した非同期応答生成（標準ガードレール付き）

        OpenAI Agents SDKを使用してユーザー入力を処理し、応答を生成する。
        このメソッドは非同期で実行され、I/Oバウンドな処理（API呼び出し）を効率的に処理する。

        Args:
            user_input (str): ユーザーからの入力テキスト

        Returns:
            str: Agents SDKからの応答テキスト

        Note:
            非同期処理について:
            - このメソッドはasync/awaitパターンを使用
            - OpenAI APIへの通信は時間がかかるため、非同期処理でブロッキングを回避
            - AgentInvoker.execute()が非同期メソッドなので、awaitキーワードで待機
            - 呼び出し元（process_input）では asyncio.run() を使用して同期的に実行

            処理フロー:
            1. AgentInvokerインスタンスを作成
            2. invoker.execute()を非同期で実行（await）
            3. OpenAI APIとの通信が完了するまで待機
            4. 応答テキストを返却
        """
        invoker = AgentInvoker(agent=self.agent, entity_name=self.entity.name)
        return await invoker.execute(user_input)

    def _preprocess_input(self, user_input: str) -> ProcessedInput:
        """
        入力の前処理とガードレールチェック

        Args:
            user_input: 元の入力テキスト

        Returns:
            処理済み入力オブジェクト
        """
        # ガードレールチェック
        guard_result = self._check_guardrails(user_input)

        if guard_result.blocked:
            return ProcessedInput(
                original_input=user_input,
                processed_input=user_input,
                is_blocked=True,
                block_reason=guard_result.message,
            )

        # 入力の正規化（必要に応じて）
        processed_input = user_input.strip()

        return ProcessedInput(
            original_input=user_input, processed_input=processed_input, is_blocked=False
        )

    def _process_with_openai(self, user_input: str) -> str:
        """
        OpenAI APIを使用した応答生成

        Args:
            user_input: 処理済み入力テキスト

        Returns:
            OpenAI APIからの応答
        """
        try:
            # システムメッセージの設定
            system_message = f"""あなたは{self.entity.name}です。
                井戸端会議のように気楽に話してください。
                不適切な内容には応答しないでください。
                日本語で回答してください。"""

            # メッセージ履歴の作成
            chat_history = [
                Message(role=RoleType.SYSTEM, content=system_message),
                Message(role=RoleType.USER, content=user_input),
            ]

            # LlmCompletionServiceを使用してOpenAI APIにリクエスト
            response = self.llm_service.retrieve_answer(chat_history)

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error for entity {self.entity.name}: {e}")
            return f"{self.entity.name}: 申し訳ありませんが、現在応答できません。しばらくしてから再度お試しください。"

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

        if moderation_result.blocked:
            # categoriesがある場合は取得、なければ空リスト
            categories = moderation_result.categories
            if not categories:
                categories = ["moderation_error"] if self.config.strict_mode else []

            # ModerationCategoryオブジェクトから名前を取得
            category_names = [cat.name for cat in categories] if categories else []

            return GuardrailResult(
                blocked=True,
                message=moderation_result.message,
                violation_categories=category_names,
            )

        return GuardrailResult(blocked=False, message="")

    def _process_default(self, user_input: str) -> str:
        """
        既存のデフォルト処理（従来のダミーテキスト）

        Args:
            user_input: 処理済み入力テキスト

        Returns:
            デフォルト応答テキスト
        """
        return f"{self.entity.name}: {user_input}について考えてみますね..."
