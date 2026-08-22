from __future__ import annotations

from dataclasses import replace

from ai_agent.domain.valueobject.game import BoardEventRecord, BoardSpaceType, GameState
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
    def select_mondai(state: GameState, mondai_id: str) -> GameState:
        """対象問題を選択し、プレイヤー駒をそのマスへ移動した状態を返す。"""
        try:
            target = state.mondai(mondai_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown mondai: {mondai_id}") from error
        if target.solved:
            raise GameDomainError(f"problem is already solved: {mondai_id}")
        return replace(
            state,
            player_position=target.position,
            selected_mondai_id=mondai_id,
            selected_line_id=None,
        )

    @staticmethod
    def select_board_space(state: GameState, space_id: str) -> GameState:
        """イベントマスへ移動し、一度だけの盤面効果を適用した状態を返す。"""
        try:
            space = state.board_space(space_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown board space: {space_id}") from error
        if space_id in state.used_board_space_ids:
            raise GameDomainError(f"board space is already used: {space_id}")

        experience_gained = 0
        recovered_hit_points = 0
        recovered_problem_count = 0
        updated_mondais = state.mondais
        try:
            space_type = BoardSpaceType(space.space_type)
        except (TypeError, ValueError) as error:
            raise GameDomainError(
                f"unsupported board space type: {space.space_type}"
            ) from error
        if space_type is BoardSpaceType.EXPERIENCE_BONUS:
            experience_gained = 10
            summary = "経験値ボーナスを獲得しました。"
        elif space_type is BoardSpaceType.REST:
            recovered_mondais = []
            for mondai in state.mondais:
                if mondai.solved or mondai.hit_points >= 3:
                    recovered_mondais.append(mondai)
                    continue
                recovered_mondais.append(
                    replace(mondai, hit_points=mondai.hit_points + 1)
                )
                recovered_hit_points += 1
                recovered_problem_count += 1
            updated_mondais = tuple(recovered_mondais)
            if recovered_problem_count:
                summary = (
                    f"未解決の問題{recovered_problem_count}件を"
                    f"1HPずつ回復しました。"
                )
            else:
                summary = "回復できる問題はありませんでした。"
        else:
            raise GameDomainError(f"unsupported board space type: {space_type}")

        event = BoardEventRecord(
            space_id=space.space_id,
            space_name=space.name,
            space_type=space_type.value,
            summary=summary,
            experience_gained=experience_gained,
            recovered_hit_points=recovered_hit_points,
            recovered_problem_count=recovered_problem_count,
        )
        return replace(
            state,
            player_position=space.position,
            experience=state.experience + experience_gained,
            mondais=updated_mondais,
            selected_mondai_id=None,
            selected_line_id=None,
            used_board_space_ids=state.used_board_space_ids + (space.space_id,),
            board_event_history=(event,) + state.board_event_history,
        )

    @staticmethod
    def select_line(state: GameState, line_id: str) -> GameState:
        """プリセットセリフを選択した状態を返す。"""
        if not any(line.line_id == line_id for line in state.preset_lines):
            raise GameDomainError(f"unknown preset line: {line_id}")
        if state.selected_mondai_id and state.mondai(state.selected_mondai_id).solved:
            raise GameDomainError("problem is already solved")
        return state.with_selection(line_id=line_id)

    @staticmethod
    def execute_skill(
        state: GameState,
        definition: SkillToolDefinition,
        *,
        target_mondai_id: str,
    ) -> tuple[GameState, SkillToolResult]:
        """1つのSkillを適用し、更新後の状態と構造化結果を返す。

        生存中の問題にSkillを実行した場合だけ、問題のHPと経験値を更新する。
        選択中の問題がある場合は、Tool入力の対象IDより選択中の問題を優先する。
        解決済み問題への実行は失敗として状態を変更しない。
        """
        target_mondai_id = state.selected_mondai_id or target_mondai_id
        try:
            target = state.mondai(target_mondai_id)
        except StopIteration as error:
            raise GameDomainError(f"unknown mondai: {target_mondai_id}") from error

        succeeded = not target.solved
        damage = min(definition.power, target.hit_points) if succeeded else 0
        experience = definition.experience if succeeded else 0
        remaining = target.hit_points - damage
        updated_target = replace(target, hit_points=remaining)
        updated_mondais = tuple(
            updated_target if mondai.mondai_id == target_mondai_id else mondai
            for mondai in state.mondais
        )
        next_state = replace(
            state,
            mondais=updated_mondais if succeeded else state.mondais,
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
            target_mondai_id=target_mondai_id,
            damage=damage,
            experience_gained=experience,
            mondai_remaining_hit_points=remaining if succeeded else target.hit_points,
            message=message,
        )
        return next_state, result
