from __future__ import annotations

from ai_agent.domain.valueobject.agent_execution import AgentRun
from ai_agent.domain.service.agent_execution import AgentExecutionService
from ai_agent.domain.service.skill_tools import GameToolSet


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
