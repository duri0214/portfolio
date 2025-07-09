import logging

from agents import Agent, Runner
from agents.guardrail import InputGuardrail, OutputGuardrail
from django.conf import settings
from openai import OpenAI

from ai_agent.domain.valueobject.input_processor import (
    GuardrailResult,
    InputProcessorConfig,
    ProcessedInput,
)
from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.chat import Message, RoleType
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
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # LlmCompletionServiceの初期化
        self.llm_config = OpenAIGptConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000,
            api_key=settings.OPENAI_API_KEY,
        )
        self.llm_service = LlmCompletionService(self.llm_config)

        # Agents SDKの初期化
        self._setup_openai_agents()

    def _setup_openai_agents(self):
        """OpenAI Agents SDKの初期化とガードレール設定"""
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
        """OpenAI Moderation APIを使用した入力ガードレール"""

        def moderation_check(context, agent, input_text):
            try:
                response = self.openai_client.moderations.create(
                    model="text-moderation-latest", input=input_text
                )

                moderation_result = response.results[0]
                if moderation_result.flagged:
                    flagged_categories = [
                        category
                        for category, flagged in moderation_result.categories.model_dump().items()
                        if flagged
                    ]
                    return {
                        "blocked": True,
                        "message": f"{self.entity.name}: 申し訳ありませんが、その内容は適切ではないため、お答えできません。",
                        "categories": flagged_categories,
                    }

                return {"blocked": False}
            except Exception as e:
                logger.warning(f"OpenAI Moderation API error: {e}")
                if self.config.strict_mode:
                    return {
                        "blocked": True,
                        "message": f"{self.entity.name}: 現在、安全性チェックが利用できません。しばらくしてから再度お試しください。",
                    }
                return {"blocked": False}

        # TODO: https://openai.github.io/openai-agents-python/ref/guardrail/#agents.guardrail.InputGuardrail
        return InputGuardrail(
            name="moderation_guardrail", guardrail_function=moderation_check
        )

    def _create_custom_guardrail(self):
        """カスタムガードレール（禁止ワード・文字数制限）"""

        def custom_check(context, agent, input_text):
            # 禁止ワードチェック
            for word in self.config.forbidden_words:
                if word.lower() in input_text.lower():
                    return {
                        "blocked": True,
                        "message": f"{self.entity.name}: 申し訳ありませんが、その内容にはお答えできません。",
                    }

            # 文字数制限チェック
            if len(input_text) > self.config.max_input_length:
                return {
                    "blocked": True,
                    "message": f"{self.entity.name}: メッセージが長すぎます。{self.config.max_input_length}文字以内でお願いします。",
                }

            # 空文字チェック
            if not input_text.strip():
                return {
                    "blocked": True,
                    "message": f"{self.entity.name}: メッセージが空です。何かお聞きしたいことがあれば教えてください。",
                }

            return {"blocked": False}

        # TODO: https://openai.github.io/openai-agents-python/ref/guardrail/#agents.guardrail.InputGuardrail
        return InputGuardrail(name="custom_guardrail", guardrail_function=custom_check)

    def _create_output_moderation_guardrail(self):
        """出力用モデレーションガードレール"""

        def output_moderation_check(context, agent, output_text):
            try:
                response = self.openai_client.moderations.create(
                    model="text-moderation-latest", input=output_text
                )

                moderation_result = response.results[0]
                if moderation_result.flagged:
                    return {
                        "blocked": True,
                        "message": f"{self.entity.name}: 申し訳ありませんが、適切な回答を生成できませんでした。別の質問をお試しください。",
                    }

                return {"blocked": False}
            except Exception as e:
                logger.warning(f"Output moderation error: {e}")
                return {"blocked": False}

        # TODO: https://openai.github.io/openai-agents-python/ref/guardrail/#agents.guardrail.OutputGuardrail
        return OutputGuardrail(
            name="output_moderation_guardrail",
            guardrail_function=output_moderation_check,
        )

    def process_input(self, user_input: str) -> str:
        """
        ユーザー入力を処理してエージェントの応答を生成

        Args:
            user_input: ユーザーからの入力テキスト

        Returns:
            エージェントからの応答テキスト
        """
        import asyncio

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
        Agents SDKを使用した応答生成（標準ガードレール付き）

        Args:
            user_input: ユーザーからの入力テキスト

        Returns:
            Agents SDKからの応答
        """
        try:
            # エージェント実行（ガードレールは自動適用）
            # TODO: https://openai.github.io/openai-agents-python/running_agents/
            result = await Runner.run(
                agent=self.agent,
                input=user_input,
                input_guardrails=self.input_guardrails,
                output_guardrails=self.output_guardrails,
            )

            return result.response

        except Exception as e:
            logger.error(f"Agents SDK error for entity {self.entity.name}: {e}")
            return f"{self.entity.name}: 申し訳ありませんが、現在応答できません。しばらくしてから再度お試しください。"

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
        try:
            response = self.openai_client.moderations.create(
                model="text-moderation-latest", input=user_input
            )

            moderation_result = response.results[0]

            if moderation_result.flagged:
                # 違反カテゴリの取得
                flagged_categories = [
                    category
                    for category, flagged in moderation_result.categories.model_dump().items()
                    if flagged
                ]

                return GuardrailResult(
                    blocked=True,
                    message=f"{self.entity.name}: 申し訳ありませんが、その内容は適切ではないため、お答えできません。",
                    violation_categories=flagged_categories,
                )

            return GuardrailResult(blocked=False, message="")

        except Exception as e:
            # Moderation APIエラー時の処理
            logger.warning(
                f"OpenAI Moderation API error for entity {self.entity.name}: {e}"
            )

            # 厳格モードの場合はエラー時もブロック
            if self.config.strict_mode:
                return GuardrailResult(
                    blocked=True,
                    message=f"{self.entity.name}: 現在、安全性チェックが利用できません。しばらくしてから再度お試しください。",
                    violation_categories=["moderation_error"],
                )

            # 非厳格モードの場合は通す
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
