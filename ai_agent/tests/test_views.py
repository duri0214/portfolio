import json
from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from ai_agent.domain.service.game_agent import GameAgentService
from ai_agent.domain.valueobject.agent_execution import (
    AgentRun,
    AgentRunStatus,
    Report,
    ToolCall,
    ToolResult,
)


async def fake_stream_selected(self, *, max_turns=10):
    target_id = self.tools.state.selected_enemy_id
    now = datetime.now(timezone.utc)
    run = AgentRun(
        run_id="stream-run-1",
        input_text="ストリーミング実行",
        max_turns=max_turns,
        status=AgentRunStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        tool_calls=(
            ToolCall(
                call_id="stream-call-1",
                name="calculate",
                arguments={"target_enemy_id": target_id, "score": 80},
                sequence=1,
            ),
        ),
        tool_results=(
            ToolResult(
                call_id="stream-call-1",
                name="calculate",
                output={
                    "display_name": "計算",
                    "success": True,
                    "target_enemy_id": target_id,
                    "damage": 1,
                    "experience_gained": 10,
                    "enemy_remaining_hit_points": 2,
                    "message": "計算が成功しました。",
                },
                succeeded=True,
                sequence=1,
            ),
        ),
        report=Report(
            output="計算で条件を確かめました。",
            status=AgentRunStatus.COMPLETED,
            tool_calls=(),
            tool_results=(),
            turns=1,
        ),
    )
    yield {"type": "run.started", "run_id": run.run_id}
    yield {
        "type": "tool.selected",
        "call_id": "stream-call-1",
        "tool_name": "calculate",
        "arguments": {"target_enemy_id": target_id, "score": 80},
        "sequence": 1,
    }
    yield {
        "type": "tool.started",
        "call_id": "stream-call-1",
        "tool_name": "calculate",
        "arguments": {"target_enemy_id": target_id, "score": 80},
        "sequence": 1,
    }
    yield {
        "type": "tool.completed",
        "call_id": "stream-call-1",
        "tool_name": "calculate",
        "output": run.tool_results[0].output,
    }
    yield {
        "type": "report.completed",
        "run_id": run.run_id,
        "status": "completed",
        "output": run.report.output,
        "error": None,
        "run": run,
    }


class AgentStreamingViewTest(TestCase):
    def test_streaming_endpoint_persists_completed_tool_history(self):
        self.client.post(
            "/ai_agent/",
            {"action": "select_enemy", "enemy_id": "enemy-language"},
        )

        with patch.object(GameAgentService, "stream_selected", fake_stream_selected):
            response = self.client.post(
                "/ai_agent/",
                {"action": "stream_agent", "line_id": "line-observe"},
            )
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn("event: tool.completed", body)
        self.assertIn("event: report.completed", body)
        report_data = next(
            json.loads(line[6:])
            for line in body.splitlines()
            if line.startswith("data: ") and '"state_token"' in line
        )

        saved = self.client.post(
            "/ai_agent/",
            {
                "action": "save_stream_state",
                "state_token": report_data["state_token"],
            },
        )
        self.assertRedirects(saved, "/ai_agent/")
        page = self.client.get("/ai_agent/")

        self.assertContains(page, "Agent実行 #1")
        self.assertContains(page, "calculate")
        self.assertContains(page, "状態変化: ダメージ 1")
        self.assertContains(page, "数値や式を計算して答えを確かめる")
        self.assertNotContains(page, "入力:")
        self.assertNotContains(page, "判定スコア")
        self.assertNotContains(page, "結果:")
