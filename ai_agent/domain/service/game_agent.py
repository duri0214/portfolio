from __future__ import annotations

from ai_agent.domain.service.agent_execution import AgentExecutionService
from ai_agent.domain.service.skill_tools import GameToolSet
from ai_agent.domain.valueobject.agent_execution import AgentRun


class GameAgentService:
    """ゲーム用Agentへ全Skill Toolを登録するアプリケーションサービス。"""

    def __init__(self, tools: GameToolSet | None = None, *, model: str = "gpt-5-mini"):
        self.tools = tools or GameToolSet()
        self.execution = AgentExecutionService(
            name="Skill Chain Game Agent",
            instructions=(
                "プレイヤーのセリフを解釈し、利用可能なSkill Toolから必要なものを選ぶ。"
                "Toolの呼び出し順は固定せず、結果に応じて追加Toolを選択する。"
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
            f"プレイヤーのセリフ: {line.text}。"
            "利用可能な6つのSkill Toolから必要なものを選び、"
            "必要なら複数Toolを順番に実行してください。"
            "問題の教科とSkillの教科は一致しなくても構いません。"
            f"Toolのtarget_enemy_idには{enemy.enemy_id}を使ってください。"
        )
        return self.run_sync(input_text, max_turns=max_turns)
