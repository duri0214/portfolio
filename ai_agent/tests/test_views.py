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
    target_id = self.tools.state.selected_mondai_id
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
                arguments={"target_mondai_id": target_id},
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
                    "target_mondai_id": target_id,
                    "damage": 1,
                    "experience_gained": 10,
                    "mondai_remaining_hit_points": 2,
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
        "arguments": {"target_mondai_id": target_id},
        "sequence": 1,
    }
    yield {
        "type": "tool.started",
        "call_id": "stream-call-1",
        "tool_name": "calculate",
        "arguments": {"target_mondai_id": target_id},
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
    def test_board_displays_special_spaces_and_persists_bonus_event(self):
        """
        シナリオ:
        - 入力: 初期状態のSkill Chain Game画面と経験値ボーナスの選択。
        - 処理: 盤面を表示し、ボーナスマスへ移動して画面を再取得する。
        - 期待値: 2種類のイベントマスが識別表示され、経験値と移動履歴が保存される。
        """
        page = self.client.get("/ai_agent/")

        self.assertContains(page, "経験値ボーナス")
        self.assertContains(page, "休憩")
        self.assertContains(page, "初回の移動で経験値+10")
        self.assertContains(page, 'name="space_id" value="board-space-bonus"')

        response = self.client.post(
            "/ai_agent/",
            {"action": "select_board_space", "space_id": "board-space-bonus"},
        )

        self.assertEqual(response.status_code, 302)
        page = self.client.get("/ai_agent/")
        self.assertContains(page, "経験値: ")
        self.assertContains(page, "経験値 +10")
        self.assertContains(page, "盤面イベント #1")
        self.assertContains(page, "使用済み")
        self.assertNotContains(page, 'name="space_id" value="board-space-bonus"')

    def test_invalid_stream_state_token_returns_an_error_redirect(self):
        """
        シナリオ:
        - 入力: 署名検証に失敗するストリーム状態Token。
        - 処理: 保存endpointへTokenを送信する。
        - 期待値: HTTP 500ではなくトップ画面へ戻り、操作エラーが表示される。
        """
        response = self.client.post(
            "/ai_agent/",
            {"action": "save_stream_state", "state_token": "invalid-token"},
        )

        self.assertEqual(response.status_code, 302)
        page = self.client.get(response["Location"])
        self.assertContains(page, "操作できません")

    def test_stale_stream_state_token_does_not_overwrite_newer_game_state(self):
        self.client.post(
            "/ai_agent/",
            {"action": "select_mondai", "mondai_id": "mondai-language"},
        )

        with patch.object(GameAgentService, "stream_selected", fake_stream_selected):
            response = self.client.post(
                "/ai_agent/",
                {"action": "stream_agent", "line_id": "line-observe"},
            )
            body = b"".join(response.streaming_content).decode("utf-8")

        state_token = next(
            json.loads(line[6:])["state_token"]
            for line in body.splitlines()
            if line.startswith("data: ") and '"state_token"' in line
        )
        self.client.post(
            "/ai_agent/",
            {"action": "select_mondai", "mondai_id": "mondai-mathematics"},
        )

        saved = self.client.post(
            "/ai_agent/",
            {"action": "save_stream_state", "state_token": state_token},
        )
        page = self.client.get(saved["Location"])

        self.assertEqual(saved.status_code, 302)
        self.assertContains(page, "ゲーム状態が更新されています")
        self.assertContains(page, "算数の問題")
        self.assertNotContains(page, "計算で条件を確かめました")

    def test_stream_state_token_can_only_be_saved_once(self):
        self.client.post(
            "/ai_agent/",
            {"action": "select_mondai", "mondai_id": "mondai-language"},
        )

        with patch.object(GameAgentService, "stream_selected", fake_stream_selected):
            response = self.client.post(
                "/ai_agent/",
                {"action": "stream_agent", "line_id": "line-observe"},
            )
            body = b"".join(response.streaming_content).decode("utf-8")

        state_token = next(
            json.loads(line[6:])["state_token"]
            for line in body.splitlines()
            if line.startswith("data: ") and '"state_token"' in line
        )
        self.client.post(
            "/ai_agent/",
            {"action": "save_stream_state", "state_token": state_token},
        )
        replayed = self.client.post(
            "/ai_agent/",
            {"action": "save_stream_state", "state_token": state_token},
        )

        page = self.client.get(replayed["Location"])
        self.assertContains(page, "すでに使用されています")
        self.assertContains(page, "Agent実行 #1")

    def test_streaming_endpoint_persists_completed_tool_history(self):
        self.client.post(
            "/ai_agent/",
            {"action": "select_mondai", "mondai_id": "mondai-language"},
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
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(saved["Location"], "/ai_agent/")
        page = self.client.get("/ai_agent/")

        self.assertContains(page, "Agent実行 #1")
        self.assertContains(
            page, "Agentが1つのSkillをチェーンしました。結果を反映しました。"
        )
        self.assertContains(page, "calculate")
        self.assertContains(page, "順番")
        self.assertContains(page, "#1")
        self.assertContains(page, "対象: 国語の問題")
        self.assertContains(page, "計算が成功しました。")
        self.assertContains(
            page,
            'title="計算: 数値や式を計算して答えを確かめる / 効果: 問題HPを1減らす"',
        )
        self.assertContains(page, "問題HP -1 / 残りHP 2 / 経験値 +10")
        self.assertContains(page, "数値や式を計算して答えを確かめる")
        self.assertNotContains(page, "入力:")
        self.assertNotContains(page, "判定スコア")
        self.assertNotContains(page, "結果:")

    def test_streaming_endpoint_keeps_six_histories_without_growing_game_cookie(self):
        mondai_ids = (
            "mondai-language",
            "mondai-language-mathematics",
            "mondai-mathematics",
            "mondai-language-science",
            "mondai-mathematics-science",
            "mondai-science",
        )

        for mondai_id in mondai_ids:
            self.client.post(
                "/ai_agent/",
                {"action": "select_mondai", "mondai_id": mondai_id},
            )
            with patch.object(
                GameAgentService, "stream_selected", fake_stream_selected
            ):
                response = self.client.post(
                    "/ai_agent/",
                    {"action": "stream_agent", "line_id": "line-observe"},
                )
                body = b"".join(response.streaming_content).decode("utf-8")
            state_token = next(
                json.loads(line[6:])["state_token"]
                for line in body.splitlines()
                if line.startswith("data: ") and '"state_token"' in line
            )
            saved = self.client.post(
                "/ai_agent/",
                {
                    "action": "save_stream_state",
                    "state_token": state_token,
                },
            )
            self.assertLess(
                len(saved.cookies["ai_agent_game_state"].value),
                4096,
            )

        page = self.client.get("/ai_agent/")
        self.assertContains(page, "Agent実行 #6")
