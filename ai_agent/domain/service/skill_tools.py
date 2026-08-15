from __future__ import annotations

from typing import Any

from agents import function_tool

from ai_agent.domain.service.game import GameService
from ai_agent.domain.valueobject.game import GameState
from ai_agent.domain.valueobject.skill_tool import (
    SkillCategory,
    SkillToolDefinition,
    SkillToolResult,
)


class SkillToolCatalog:
    """6つのSkill Toolの実装名と表示名を一元管理する。"""

    _DEFINITIONS = (
        SkillToolDefinition(
            "analyze_reading", "読解分析", SkillCategory.LANGUAGE, 1, 10
        ),
        SkillToolDefinition(
            "analyze_expression", "表現分析", SkillCategory.LANGUAGE, 2, 15
        ),
        SkillToolDefinition("calculate", "計算", SkillCategory.MATHEMATICS, 1, 10),
        SkillToolDefinition("mental_math", "暗算", SkillCategory.MATHEMATICS, 2, 15),
        SkillToolDefinition("infer_cause", "原因推論", SkillCategory.SCIENCE, 1, 10),
        SkillToolDefinition(
            "analyze_observation", "観察分析", SkillCategory.SCIENCE, 2, 15
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


class GameToolSet:
    """GameServiceをSDK Function Toolへ変換するアダプター。

    Attributes:
        state: Tool実行で更新される現在のゲーム状態。
    """

    def __init__(self, state: GameState | None = None) -> None:
        self.state = state or GameService.create_game()

    def select_enemy(self, enemy_id: str) -> dict[str, Any]:
        """Agentから敵選択を受け取り、選択後の状態を返す。"""
        self.state = GameService.select_enemy(self.state, enemy_id)
        return {"selected_enemy_id": enemy_id}

    def select_line(self, line_id: str) -> dict[str, Any]:
        """Agentからプリセットセリフ選択を受け取り、選択後の状態を返す。"""
        self.state = GameService.select_line(self.state, line_id)
        return {"selected_line_id": line_id}

    def execute(
        self, tool_name: str, target_enemy_id: str, score: int
    ) -> dict[str, Any]:
        """指定されたToolだけを実行し、状態と結果を更新する。"""
        definition = SkillToolCatalog.get(tool_name)
        self.state, result = GameService.execute_skill(
            self.state,
            definition,
            target_enemy_id=target_enemy_id,
            score=score,
        )
        return result.to_dict()

    def analyze_reading(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """国語の読解分析Tool。"""
        return self.execute("analyze_reading", target_enemy_id, score)

    def analyze_expression(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """国語の表現分析Tool。"""
        return self.execute("analyze_expression", target_enemy_id, score)

    def calculate(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """算数の計算Tool。"""
        return self.execute("calculate", target_enemy_id, score)

    def mental_math(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """算数の暗算Tool。"""
        return self.execute("mental_math", target_enemy_id, score)

    def infer_cause(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """理科の原因推論Tool。"""
        return self.execute("infer_cause", target_enemy_id, score)

    def analyze_observation(self, target_enemy_id: str, score: int) -> dict[str, Any]:
        """理科の観察分析Tool。"""
        return self.execute("analyze_observation", target_enemy_id, score)

    def function_tools(self) -> list[Any]:
        """Agentに登録できる6つのFunction Toolを返す。"""
        return [
            function_tool(self.analyze_reading),
            function_tool(self.analyze_expression),
            function_tool(self.calculate),
            function_tool(self.mental_math),
            function_tool(self.infer_cause),
            function_tool(self.analyze_observation),
        ]
