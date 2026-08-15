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
    def select_enemy(state: GameState, enemy_id: str) -> GameState:
        """対象敵を選択した状態を返す。"""
        if not any(enemy.enemy_id == enemy_id for enemy in state.enemies):
            raise GameDomainError(f"unknown enemy: {enemy_id}")
        return state.with_selection(enemy_id=enemy_id)

    @staticmethod
    def select_line(state: GameState, line_id: str) -> GameState:
        """プリセットセリフを選択した状態を返す。"""
        if not any(line.line_id == line_id for line in state.preset_lines):
            raise GameDomainError(f"unknown preset line: {line_id}")
        return state.with_selection(line_id=line_id)

    @staticmethod
    def execute_skill(
        state: GameState,
        definition: SkillToolDefinition,
        *,
        target_enemy_id: str,
        score: int,
    ) -> tuple[GameState, SkillToolResult]:
        """1つのSkillを適用し、更新後の状態と構造化結果を返す。

        scoreが60未満なら失敗として状態を変更しない。成功時だけ敵の体力と経験値を
        更新するため、失敗Toolを含むChainでも結果を明確に追跡できる。
        """
        if not 0 <= score <= 100:
            raise GameDomainError("score must be between 0 and 100")
        try:
            target = state.enemy(target_enemy_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown enemy: {target_enemy_id}") from error
        if target.category is not definition.category:
            raise GameDomainError(
                f"{definition.name} cannot target {target.category.value} enemy"
            )

        succeeded = score >= 60 and not target.defeated
        damage = definition.power if succeeded else 0
        experience = definition.experience if succeeded else 0
        remaining = max(target.hit_points - damage, 0)
        updated_target = replace(target, hit_points=remaining)
        updated_enemies = tuple(
            updated_target if enemy.enemy_id == target_enemy_id else enemy
            for enemy in state.enemies
        )
        next_state = replace(
            state,
            enemies=updated_enemies if succeeded else state.enemies,
            experience=state.experience + experience,
            tool_history=state.tool_history + (definition.name,),
        )
        message = (
            f"{definition.display_name}が成功し、{target.name}に{damage}ダメージ。"
            if succeeded
            else f"{definition.display_name}は失敗した。敵への効果はない。"
        )
        result = SkillToolResult(
            tool_name=definition.name,
            display_name=definition.display_name,
            success=succeeded,
            target_enemy_id=target_enemy_id,
            damage=damage,
            experience_gained=experience,
            enemy_remaining_hit_points=remaining if succeeded else target.hit_points,
            message=message,
        )
        return next_state, result
