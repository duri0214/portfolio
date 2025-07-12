import logging
import os
from typing import Callable

from openai import OpenAI

from lib.llm.valueobject.agent import ModerationResult, ModerationCategory

logger = logging.getLogger(__name__)


class ModerationService:
    """
    Moderation機能を提供するサービス
    OpenAI Moderation APIを使用した入力・出力のチェック機能
    """

    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _check_moderation(
        self,
        text: str,
        entity_name: str,
        blocked_message: str,
        strict_mode: bool = False,
    ) -> ModerationResult:
        """
        OpenAI Moderation APIを使用したテキストのモデレーションチェック

        Args:
            text: チェック対象のテキスト
            entity_name: エンティティ名
            blocked_message: ブロック時のメッセージ
            strict_mode: 厳格モードかどうか

        Returns:
            モデレーション結果
        """
        try:
            response = self.openai_client.moderations.create(
                model="text-moderation-latest", input=text
            )

            moderation_result = response.results[0]
            if moderation_result.flagged:
                flagged_categories = [
                    ModerationCategory(name=category)
                    for category, flagged in moderation_result.categories.model_dump().items()
                    if flagged
                ]
                return ModerationResult(
                    blocked=True,
                    message=f"{entity_name}: {blocked_message}",
                    categories=flagged_categories,
                )

            return ModerationResult(blocked=False)
        except Exception as e:
            logger.warning(f"OpenAI Moderation API error: {e}")
            if strict_mode:
                return ModerationResult(
                    blocked=True,
                    message=f"{entity_name}: 現在、安全性チェックが利用できません。しばらくしてから再度お試しください。",
                )
            return ModerationResult(blocked=False)

    def check_input_moderation(
        self, input_text: str, entity_name: str, strict_mode: bool = False
    ) -> ModerationResult:
        """
        入力テキストのモデレーションチェック

        Args:
            input_text: チェック対象の入力テキスト
            entity_name: エンティティ名
            strict_mode: 厳格モードかどうか

        Returns:
            モデレーション結果
        """
        return self._check_moderation(
            input_text,
            entity_name,
            "申し訳ありませんが、その内容は適切ではないため、お答えできません。",
            strict_mode,
        )

    def check_output_moderation(
        self, output_text: str, entity_name: str
    ) -> ModerationResult:
        """
        出力テキストのモデレーションチェック

        Args:
            output_text: チェック対象の出力テキスト
            entity_name: エンティティ名

        Returns:
            モデレーション結果
        """
        return self._check_moderation(
            output_text,
            entity_name,
            "申し訳ありませんが、適切な回答を生成できませんでした。別の質問をお試しください。",
        )

    @staticmethod
    def _convert_moderation_result_to_dict(
        result: ModerationResult,
    ) -> dict[str, bool | str]:
        """
        ModerationResultをOpenAI Agents SDKが期待する形式に変換

        Args:
            result: モデレーション結果

        Returns:
            変換された辞書
        """
        response = {"blocked": result.blocked, "message": result.message}
        # categoriesがある場合はメッセージに含める
        if result.categories:
            category_names = [category.name for category in result.categories]
            response["message"] = (
                f"{result.message} (カテゴリ: {', '.join(category_names)})"
            )
        return response

    def create_moderation_guardrail(
        self, entity_name: str, strict_mode: bool = False
    ) -> Callable:
        """
        OpenAI Moderation APIを使用した入力ガードレール関数を作成

        Args:
            entity_name: エンティティ名
            strict_mode: 厳格モードかどうか

        Returns:
            ガードレール関数 (context, agent, input_text) -> dict[str, bool | str]
            OpenAI Agents SDKで使用される入力チェック用の関数
        """

        def moderation_check(_, __, input_text: str) -> dict[str, bool | str]:
            result = self.check_input_moderation(input_text, entity_name, strict_mode)
            return self._convert_moderation_result_to_dict(result)

        return moderation_check

    def create_output_moderation_guardrail(self, entity_name: str) -> Callable:
        """
        出力用モデレーションガードレール関数を作成

        Args:
            entity_name: エンティティ名

        Returns:
            出力ガードレール関数 (context, agent, output_text) -> dict[str, bool | str]
            OpenAI Agents SDKで使用される出力チェック用の関数
        """

        def output_moderation_check(_, __, output_text: str) -> dict[str, bool | str]:
            result = self.check_output_moderation(output_text, entity_name)
            return self._convert_moderation_result_to_dict(result)

        return output_moderation_check
