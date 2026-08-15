from __future__ import annotations

from dataclasses import replace

from ai_agent.domain.valueobject.game import GameState
from ai_agent.domain.valueobject.skill_tool import (
    SkillToolDefinition,
    SkillToolResult,
)


class GameDomainError(ValueError):
    """ゲームの選択やSkill実行がドメインルールに違反した場合の例外。"""


class GameService:
    """ゲーム状態の選択とSkill実行を担うドメインサービス。

    AgentのTool呼び出し順は決めず、呼び出されたTool 1回ごとに新しい状態を返す。
    そのため、単一Toolでも複数ToolのChainでも同じルールで処理できる。
    """

    @staticmethod
    def create_game() -> GameState:
        """新しいゲームの初期状態を返す。"""
        return GameState.initial()

    @staticmethod
    def select_issue(state: GameState, issue_id: str) -> GameState:
        """対象問題を選択し、プレイヤー駒をそのマスへ移動した状態を返す。"""
        try:
            target = state.issue(issue_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown issue: {issue_id}") from error
        if target.solved:
            raise GameDomainError(f"problem is already solved: {issue_id}")
        return replace(
            state,
            player_position=target.position,
            selected_issue_id=issue_id,
            selected_line_id=None,
        )

    @staticmethod
    def select_line(state: GameState, line_id: str) -> GameState:
        """プリセットセリフを選択した状態を返す。"""
        if not any(line.line_id == line_id for line in state.preset_lines):
            raise GameDomainError(f"unknown preset line: {line_id}")
        if state.selected_issue_id and state.issue(state.selected_issue_id).solved:
            raise GameDomainError("problem is already solved")
        return state.with_selection(line_id=line_id)

    @staticmethod
    def execute_skill(
        state: GameState,
        definition: SkillToolDefinition,
        *,
        target_issue_id: str,
    ) -> tuple[GameState, SkillToolResult]:
        """1つのSkillを適用し、更新後の状態と構造化結果を返す。

        生存中の問題にSkillを実行した場合だけ、問題のHPと経験値を更新する。
        選択中の問題がある場合は、Tool入力の対象IDより選択中の問題を優先する。
        解決済み問題への実行は失敗として状態を変更しない。
        """
        target_issue_id = state.selected_issue_id or target_issue_id
        try:
            target = state.issue(target_issue_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown issue: {target_issue_id}") from error

        succeeded = not target.solved
        damage = min(definition.power, target.hit_points) if succeeded else 0
        experience = definition.experience if succeeded else 0
        remaining = target.hit_points - damage
        updated_target = replace(target, hit_points=remaining)
        updated_issues = tuple(
            updated_target if issue.issue_id == target_issue_id else issue
            for issue in state.issues
        )
        next_state = replace(
            state,
            issues=updated_issues if succeeded else state.issues,
            experience=state.experience + experience,
            tool_history=state.tool_history + (definition.name,),
        )
        message = (
            f"{definition.display_name}が成功し、{target.name}に{damage}ダメージ。"
            if succeeded
            else f"{definition.display_name}は失敗した。問題への効果はない。"
        )
        result = SkillToolResult(
            tool_name=definition.name,
            display_name=definition.display_name,
            success=succeeded,
            target_issue_id=target_issue_id,
            damage=damage,
            experience_gained=experience,
            issue_remaining_hit_points=remaining if succeeded else target.hit_points,
            message=message,
        )
        return next_state, result
