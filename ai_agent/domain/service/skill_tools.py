from __future__ import annotations

import json
from typing import Any

from agents import function_tool
from agents.tool_guardrails import ToolGuardrailFunctionOutput, ToolInputGuardrail

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.safety import SafetyPolicy
from ai_agent.domain.valueobject.game import GameState
from ai_agent.domain.valueobject.safety import GuardrailResult, GuardrailStage
from ai_agent.domain.valueobject.skill_tool import (
    SkillCategory,
    SkillToolDefinition,
    SkillToolResult,
)


class SkillToolCatalog:
    """6つのSkill Toolの実装名と表示名を一元管理する。"""

    _DEFINITIONS = (
        SkillToolDefinition(
            "analyze_reading",
            "読解分析",
            SkillCategory.LANGUAGE,
            1,
            10,
            "問題文の要点と条件を整理する",
        ),
        SkillToolDefinition(
            "analyze_expression",
            "表現分析",
            SkillCategory.LANGUAGE,
            2,
            15,
            "言葉や表現の関係を読み解く",
        ),
        SkillToolDefinition(
            "calculate",
            "計算",
            SkillCategory.MATHEMATICS,
            1,
            10,
            "数値や式を計算して答えを確かめる",
        ),
        SkillToolDefinition(
            "compare_quantities",
            "数量比較",
            SkillCategory.MATHEMATICS,
            2,
            15,
            "数量や条件を比べて大小・差・割合の関係を整理する",
        ),
        SkillToolDefinition(
            "infer_cause",
            "原因推論",
            SkillCategory.SCIENCE,
            1,
            10,
            "現象から原因と結果の関係を推論する",
        ),
        SkillToolDefinition(
            "analyze_observation",
            "観察分析",
            SkillCategory.SCIENCE,
            2,
            15,
            "観察結果から特徴や規則性を整理する",
        ),
    )

    @classmethod
    def definitions(cls) -> tuple[SkillToolDefinition, ...]:
        """UI表示やAgent設定に使うTool定義を返す。"""
        return cls._DEFINITIONS

    @classmethod
    def get(cls, name: str) -> SkillToolDefinition:
        """実装名からTool定義を返す。"""
        try:
            return next(
                definition for definition in cls._DEFINITIONS if definition.name == name
            )
        except StopIteration as error:
            raise ValueError(f"unknown skill tool: {name}") from error

    @classmethod
    def expected_tool_chain(
        cls, category: SkillCategory, line_id: str
    ) -> tuple[str, ...]:
        """代表シナリオの評価に使う教科別Tool Chainを返す。

        これはAgentの実行順を固定する設定ではなく、プリセットセリフの
        代表ケースをテストで評価するための期待値です。
        """
        category = SkillCategory(category)
        chains = {
            SkillCategory.LANGUAGE: {
                "line-challenge": ("analyze_expression",),
                "line-observe": ("analyze_reading",),
                "line-chain": ("analyze_reading", "analyze_expression"),
            },
            SkillCategory.MATHEMATICS: {
                "line-challenge": ("calculate",),
                "line-observe": ("compare_quantities",),
                "line-chain": ("calculate", "compare_quantities"),
            },
            SkillCategory.SCIENCE: {
                "line-challenge": ("infer_cause",),
                "line-observe": ("analyze_observation",),
                "line-chain": ("infer_cause", "analyze_observation"),
            },
        }
        try:
            return chains[category][line_id]
        except KeyError as error:
            raise ValueError(
                f"unknown preset line or skill category: {line_id}, {category}"
            ) from error


class GameToolSet:
    """GameServiceをSDK Function Toolへ変換するアダプター。

    Attributes:
        state: Tool実行で更新される現在のゲーム状態。
    """

    def __init__(
        self,
        state: GameState | None = None,
        *,
        safety_policy: SafetyPolicy | None = None,
    ) -> None:
        self.state = state or GameService.create_game()
        self.safety_policy = safety_policy or SafetyPolicy()

    def select_mondai(self, mondai_id: str) -> dict[str, Any]:
        """Agentから問題選択を受け取り、選択後の状態を返す。"""
        self.state = GameService.select_mondai(self.state, mondai_id)
        return {"selected_mondai_id": mondai_id}

    def select_line(self, line_id: str) -> dict[str, Any]:
        """Agentからプリセットセリフ選択を受け取り、選択後の状態を返す。"""
        self.state = GameService.select_line(self.state, line_id)
        return {"selected_line_id": line_id}

    def execute(self, tool_name: str, target_mondai_id: str) -> dict[str, Any]:
        """指定されたToolだけを実行し、状態と結果を更新する。"""
        definition = SkillToolCatalog.get(tool_name)
        self._validate_tool_arguments(tool_name, {"target_mondai_id": target_mondai_id})
        self.state, result = GameService.execute_skill(
            self.state,
            definition,
            target_mondai_id=target_mondai_id,
        )
        return result.to_dict()

    def analyze_reading(self, target_mondai_id: str) -> dict[str, Any]:
        """国語の読解分析Tool。"""
        return self.execute("analyze_reading", target_mondai_id)

    def analyze_expression(self, target_mondai_id: str) -> dict[str, Any]:
        """国語の表現分析Tool。"""
        return self.execute("analyze_expression", target_mondai_id)

    def calculate(self, target_mondai_id: str) -> dict[str, Any]:
        """算数の計算Tool。"""
        return self.execute("calculate", target_mondai_id)

    def compare_quantities(self, target_mondai_id: str) -> dict[str, Any]:
        """算数の数量比較Tool。"""
        return self.execute("compare_quantities", target_mondai_id)

    def infer_cause(self, target_mondai_id: str) -> dict[str, Any]:
        """理科の原因推論Tool。"""
        return self.execute("infer_cause", target_mondai_id)

    def analyze_observation(self, target_mondai_id: str) -> dict[str, Any]:
        """理科の観察分析Tool。"""
        return self.execute("analyze_observation", target_mondai_id)

    def function_tools(self) -> list[Any]:
        """Agentに登録できる6つのFunction Toolを返す。"""
        handlers = (
            self.analyze_reading,
            self.analyze_expression,
            self.calculate,
            self.compare_quantities,
            self.infer_cause,
            self.analyze_observation,
        )
        tool_input_guardrail = ToolInputGuardrail(
            self._game_tool_input_guardrail,
            name="game_tool_input",
        )
        tool_output_guardrail = self.safety_policy.tool_output_guardrail()
        tools = []
        for handler in handlers:
            tool = function_tool(handler)
            tool.tool_input_guardrails = [tool_input_guardrail]
            tool.tool_output_guardrails = [tool_output_guardrail]
            tools.append(tool)
        return tools

    def _validate_tool_arguments(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> None:
        """直接呼び出しでもSDKと同じTool引数の安全性を適用する。"""
        result = self._game_tool_input_result(tool_name, arguments)
        if not result.allowed:
            raise ValueError(result.reason)

    def _game_tool_input_guardrail(self, data: Any) -> ToolGuardrailFunctionOutput:
        tool_name = str(data.context.tool_name)
        try:
            arguments = json.loads(data.context.tool_arguments)
        except (TypeError, json.JSONDecodeError):
            result = GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason=f"{tool_name}の引数は有効なJSONではありません",
            )
        else:
            result = self._game_tool_input_result(tool_name, arguments)
        if result.allowed:
            return ToolGuardrailFunctionOutput.allow(output_info=result.to_dict())
        return ToolGuardrailFunctionOutput.raise_exception(output_info=result.to_dict())

    def _game_tool_input_result(
        self, tool_name: str, arguments: Any
    ) -> GuardrailResult:
        result = self.safety_policy.check_tool_arguments(tool_name, arguments)
        if not result.allowed:
            return result
        if not isinstance(arguments, dict):
            return GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason=f"{tool_name}の引数はJSONオブジェクトで指定してください",
            )
        try:
            SkillToolCatalog.get(tool_name)
        except ValueError as error:
            return GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason=str(error),
            )
        target_mondai_id = arguments.get("target_mondai_id")
        if not isinstance(target_mondai_id, str) or not target_mondai_id.strip():
            return GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason="Tool引数target_mondai_idが不正です",
            )
        try:
            self.state.mondai(target_mondai_id)
        except StopIteration:
            return GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason=f"unknown mondai: {target_mondai_id}",
            )
        if (
            self.state.selected_mondai_id
            and target_mondai_id != self.state.selected_mondai_id
        ):
            return GuardrailResult(
                stage=GuardrailStage.TOOL_INPUT,
                allowed=False,
                reason="選択中の問題以外をToolの対象にはできません",
            )
        return result
