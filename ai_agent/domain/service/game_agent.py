from __future__ import annotations

import json

from ai_agent.domain.service.agent_execution import AgentExecutionService
from ai_agent.domain.service.skill_tools import GameToolSet, SkillToolCatalog
from ai_agent.domain.valueobject.agent_execution import AgentRun
from ai_agent.domain.valueobject.game import (
    AgentExecutionRecord,
    GameState,
    ToolExecutionRecord,
)


class GameAgentService:
    """ゲーム用Agentへ全Skill Toolを登録するアプリケーションサービス。"""

    def __init__(self, tools: GameToolSet | None = None, *, model: str = "gpt-5-mini"):
        self.tools = tools or GameToolSet()
        self.execution = AgentExecutionService(
            name="Skill Chain Game Agent",
            instructions=(
                "プレイヤーのセリフを解釈し、利用可能なSkill Toolから必要なものを選ぶ。"
                "Toolの呼び出し順は固定せず、結果に応じて追加Toolを選択する。"
                "実行後は、選択理由、行った処理、得られた結果を日本語で簡潔に説明する。"
            ),
            tools=self.tools.function_tools(),
            model=model,
        )

    async def run(self, input_text: str, *, max_turns: int = 10) -> AgentRun:
        """Agentを実行し、Tool更新後のゲーム状態を保持した実行結果を返す。"""
        return await self.execution.run(input_text, max_turns=max_turns)

    def run_sync(self, input_text: str, *, max_turns: int = 10) -> AgentRun:
        """同期ViewからAgentを実行する。"""
        return self.execution.run_sync(input_text, max_turns=max_turns)

    def run_selected(self, *, max_turns: int = 10) -> AgentRun:
        """選択済みの問題とセリフをAgentへ渡し、Tool選択を委ねる。"""
        state = self.tools.state
        if not state.selected_enemy_id or not state.selected_line_id:
            raise ValueError("問題とセリフを選択してから実行してください")
        enemy = state.enemy(state.selected_enemy_id)
        line = next(
            line
            for line in state.preset_lines
            if line.line_id == state.selected_line_id
        )
        input_text = (
            f"対象の問題: {enemy.enemy_id} ({enemy.name})。"
            f"対象の教科: {enemy.category_display_name}。"
            f"プレイヤーの選択意図: {line.label}。"
            f"プレイヤーのセリフ: {line.text}。"
            f"選択意図の説明: {line.description}"
            "利用可能な6つのSkill Toolから必要なものを選び、"
            "必要なら複数Toolを順番に実行してください。"
            "問題の教科とSkillの教科は一致しなくても構いません。"
            f"Toolのtarget_enemy_idには{enemy.enemy_id}を使ってください。"
        )
        return self.run_sync(input_text, max_turns=max_turns)

    @staticmethod
    def create_execution_record(
        state: GameState, run: AgentRun
    ) -> AgentExecutionRecord:
        """AgentRunを画面表示用のゲーム実行記録へ変換する。"""
        if not state.selected_enemy_id or not state.selected_line_id:
            raise ValueError("問題とセリフを選択してから実行してください")
        problem = state.enemy(state.selected_enemy_id)
        line = next(
            line
            for line in state.preset_lines
            if line.line_id == state.selected_line_id
        )
        calls_by_id = {call.call_id: call for call in run.tool_calls}
        steps = tuple(
            GameAgentService._create_tool_record(state, result, calls_by_id)
            for result in run.tool_results
        )
        return AgentExecutionRecord(
            run_id=run.run_id,
            problem_id=problem.enemy_id,
            problem_name=problem.name,
            problem_subjects=problem.category_display_name,
            line_label=line.label,
            line_text=line.text,
            status=run.status.value,
            explanation=GameAgentService._compact_text(run.report.output)
            or "Agentから最終説明は返りませんでした。",
            steps=steps,
            error=GameAgentService._compact_text(run.report.error) or None,
        )

    @staticmethod
    def _create_tool_record(state, result, calls_by_id):
        call = calls_by_id.get(result.call_id)
        arguments = call.arguments if call else {}
        payload = result.output
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"message": payload}
        if not isinstance(payload, dict):
            payload = {"message": str(payload)}
        target_id = str(
            payload.get("target_enemy_id")
            or arguments.get("target_enemy_id")
            or state.selected_enemy_id
        )
        try:
            target = state.enemy(target_id)
        except StopIteration:
            target = state.enemy(state.selected_enemy_id)
        try:
            definition = SkillToolCatalog.get(result.name)
            display_name = definition.display_name
            operation = definition.description
        except ValueError:
            display_name = result.name
            operation = "Skill Toolを実行して結果を確認する"
        return ToolExecutionRecord(
            sequence=result.sequence,
            tool_name=result.name,
            display_name=str(payload.get("display_name") or display_name),
            operation=operation,
            target_problem_name=target.name,
            input_summary=GameAgentService._format_input(target.name, arguments),
            success=bool(payload.get("success", result.succeeded)),
            result_summary=GameAgentService._compact_text(
                payload.get("message") or result.error or payload
            ),
            damage=int(payload.get("damage", 0)),
            experience_gained=int(payload.get("experience_gained", 0)),
            remaining_hit_points=int(
                payload.get("enemy_remaining_hit_points", target.hit_points)
            ),
        )

    @staticmethod
    def _format_input(target_name: str, arguments: dict) -> str:
        score = arguments.get("score")
        if score is None:
            return f"対象: {target_name}"
        return f"対象: {target_name} / 判定スコア: {score}"

    @staticmethod
    def _compact_text(value, limit: int = 800) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=True, default=str)
        return value[:limit]
