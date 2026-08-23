from __future__ import annotations

import json

from ai_agent.domain.service.agent_execution import AgentExecutionService
from ai_agent.domain.service.skill_tools import GameToolSet, SkillToolCatalog
from ai_agent.domain.valueobject.agent_execution import (
    AgentRun,
    ToolChainEvaluation,
)
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
                "Tool結果で問題の残りHPが0になったら、追加Toolを呼ばずに終了する。"
                "実行後は、選択理由、行った処理、得られた結果を日本語で簡潔に説明する。"
            ),
            tools=self.tools.function_tools(),
            model=model,
            safety_policy=self.tools.safety_policy,
        )

    async def run(self, input_text: str, *, max_turns: int = 10) -> AgentRun:
        """Agentを実行し、Tool更新後のゲーム状態を保持した実行結果を返す。"""
        return await self.execution.run(input_text, max_turns=max_turns)

    def run_sync(self, input_text: str, *, max_turns: int = 10) -> AgentRun:
        """同期ViewからAgentを実行する。"""
        return self.execution.run_sync(input_text, max_turns=max_turns)

    def run_selected(self, *, max_turns: int = 10) -> AgentRun:
        """選択済みの問題とセリフをAgentへ渡し、Tool選択を委ねる。"""
        return self.run_sync(self._selected_input(), max_turns=max_turns)

    async def stream_selected(self, *, max_turns: int = 10):
        """選択済みの問題をTool単位の意味イベントとして返す。"""
        state = self.tools.state
        async for event in self.execution.stream(
            self._selected_input(), max_turns=max_turns
        ):
            if event["type"] not in {"tool.selected", "tool.completed", "tool.failed"}:
                yield event
                continue
            tool_name = event.get("tool_name", "")
            try:
                definition = SkillToolCatalog.get(tool_name)
                event = {
                    **event,
                    "display_name": definition.display_name,
                    "operation": definition.description,
                    "power": definition.power,
                }
            except ValueError:
                event = dict(event)
            if event["type"] == "tool.selected":
                event["input_summary"] = self._format_input(
                    self._target_name(state, event.get("arguments", {})),
                    event.get("arguments", {}),
                )
            elif event["type"] in {"tool.completed", "tool.failed"}:
                event["result_summary"] = self._result_summary(event)
            yield event
            if event["type"] == "tool.selected":
                yield {
                    "type": "tool.started",
                    "call_id": event["call_id"],
                    "tool_name": tool_name,
                    "display_name": event.get("display_name", tool_name),
                    "operation": event.get("operation", ""),
                    "power": event.get("power"),
                    "arguments": event.get("arguments", {}),
                    "input_summary": event.get("input_summary", ""),
                    "sequence": event.get("sequence", 0),
                }

    def _selected_input(self) -> str:
        """選択中の問題とセリフからAgent入力を組み立てる。"""
        state = self.tools.state
        if not state.selected_mondai_id or not state.selected_line_id:
            raise ValueError("問題とセリフを選択してから実行してください")
        mondai = state.mondai(state.selected_mondai_id)
        line = next(
            line
            for line in state.preset_lines
            if line.line_id == state.selected_line_id
        )
        input_text = (
            f"対象の問題: {mondai.mondai_id} ({mondai.name})。"
            f"対象の教科: {mondai.category_display_name}。"
            f"プレイヤーの選択意図: {line.label}。"
            f"プレイヤーのセリフ: {line.text}。"
            f"選択意図の説明: {line.description}"
            "利用可能な6つのSkill Toolから必要なものを選び、"
            "必要なら複数Toolを順番に実行してください。"
            "問題の教科とSkillの教科は一致しなくても構いません。"
            f"Toolのtarget_mondai_idには{mondai.mondai_id}を使ってください。"
        )
        return input_text

    @staticmethod
    def create_execution_record(
        state: GameState, run: AgentRun
    ) -> AgentExecutionRecord:
        """AgentRunを画面表示用のゲーム実行記録へ変換する。"""
        if not state.selected_mondai_id or not state.selected_line_id:
            raise ValueError("問題とセリフを選択してから実行してください")
        problem = state.mondai(state.selected_mondai_id)
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
            problem_id=problem.mondai_id,
            problem_name=problem.name,
            problem_subjects=problem.category_display_name,
            line_label=line.label,
            line_text=line.text,
            status=run.status.value,
            explanation=run.report.output,
            steps=steps,
            error=run.report.error or None,
            agent_run=run,
        )

    @staticmethod
    def expected_tool_chain(state) -> tuple[str, ...]:
        """選択中の問題とセリフに対応する代表Tool Chainを返す。"""
        if not state.selected_mondai_id or not state.selected_line_id:
            raise ValueError("問題とセリフを選択してからTool Chainを評価してください")
        problem = state.mondai(state.selected_mondai_id)
        return SkillToolCatalog.expected_tool_chain(
            problem.category, state.selected_line_id
        )

    @staticmethod
    def evaluate_tool_chain(state, run: AgentRun) -> ToolChainEvaluation:
        """AgentRunのTool順をプリセットセリフの代表ケースと比較する。"""
        expected = GameAgentService.expected_tool_chain(state)
        actual = tuple(call.name for call in run.tool_calls)
        return ToolChainEvaluation(
            line_id=state.selected_line_id,
            mondai_id=state.selected_mondai_id,
            expected=expected,
            actual=actual,
            matched=actual == expected,
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
            payload.get("target_mondai_id")
            or arguments.get("target_mondai_id")
            or state.selected_mondai_id
        )
        try:
            target = state.mondai(target_id)
        except StopIteration:
            target = state.mondai(state.selected_mondai_id)
        try:
            definition = SkillToolCatalog.get(result.name)
            display_name = definition.display_name
            operation = definition.description
            power = definition.power
        except ValueError:
            display_name = result.name
            operation = "Skill Toolを実行して結果を確認する"
            power = 0
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
            power=power,
            damage=int(payload.get("damage", 0)),
            experience_gained=int(payload.get("experience_gained", 0)),
            remaining_hit_points=int(
                payload.get("mondai_remaining_hit_points", target.hit_points)
            ),
        )

    @staticmethod
    def _format_input(target_name: str, arguments: dict) -> str:
        return f"対象: {target_name}"

    @staticmethod
    def _target_name(state, arguments: dict) -> str:
        target_id = str(arguments.get("target_mondai_id", ""))
        try:
            return state.mondai(target_id).name
        except StopIteration:
            return state.mondai(state.selected_mondai_id).name

    @classmethod
    def _result_summary(cls, event: dict) -> str:
        payload = event.get("output")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"message": payload}
        if not isinstance(payload, dict):
            payload = {"message": payload}
        return cls._compact_text(
            payload.get("message") or event.get("error") or payload
        )

    @staticmethod
    def _compact_text(value, limit: int = 800) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=True, default=str)
        return value[:limit]
