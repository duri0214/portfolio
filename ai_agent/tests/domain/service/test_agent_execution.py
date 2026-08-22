import asyncio
from types import SimpleNamespace

from agents import function_tool
from django.test import SimpleTestCase

from ai_agent.domain.service.agent_execution import AgentExecutionService
from ai_agent.domain.valueobject.agent_execution import AgentRunStatus


@function_tool
def lookup_skill(topic: str) -> str:
    """テスト用のFunction Tool。"""
    return f"result:{topic}"


class FakeRunner:
    received_agent = None
    received_input = None
    received_max_turns = None

    @classmethod
    async def run(cls, agent, input_text, *, max_turns):
        cls.received_agent = agent
        cls.received_input = input_text
        cls.received_max_turns = max_turns
        return SimpleNamespace(
            new_items=[
                SimpleNamespace(
                    type="tool_call_item",
                    raw_item=SimpleNamespace(
                        call_id="call-1",
                        name="lookup_skill",
                        arguments='{"topic": "science"}',
                    ),
                ),
                SimpleNamespace(
                    type="tool_call_output_item",
                    raw_item=SimpleNamespace(call_id="call-1", output="result:science"),
                ),
            ],
            raw_responses=[object(), object()],
            final_output="最終レポート",
        )


class FakeStreamingResult:
    def __init__(self):
        self.new_items = [
            SimpleNamespace(
                type="tool_call_item",
                raw_item={
                    "call_id": "call-stream-1",
                    "name": "lookup_skill",
                    "arguments": '{"topic": "science"}',
                },
            ),
            SimpleNamespace(
                type="tool_call_output_item",
                raw_item={"call_id": "call-stream-1", "output": "result:science"},
            ),
        ]
        self.raw_responses = [object()]
        self.final_output = "ストリーミング最終レポート"

    async def stream_events(self):
        yield SimpleNamespace(
            type="run_item_stream_event",
            name="tool_called",
            item=SimpleNamespace(
                raw_item=self.new_items[0].raw_item,
            ),
        )
        yield SimpleNamespace(
            type="run_item_stream_event",
            name="tool_output",
            item=SimpleNamespace(
                raw_item=self.new_items[1].raw_item,
                output="result:science",
            ),
        )


class StreamingRunner:
    @classmethod
    def run_streamed(cls, agent, input_text, *, max_turns):
        return FakeStreamingResult()


class FailingStreamingResult(FakeStreamingResult):
    async def stream_events(self):
        yield SimpleNamespace(
            type="run_item_stream_event",
            name="tool_called",
            item=SimpleNamespace(raw_item=self.new_items[0].raw_item),
        )
        raise RuntimeError("stream interrupted")


class FailingStreamingRunner:
    @classmethod
    def run_streamed(cls, agent, input_text, *, max_turns):
        return FailingStreamingResult()


class FailingRunner:
    @staticmethod
    async def run(agent, input_text, *, max_turns):
        raise RuntimeError("provider unavailable")


class SlowRunner:
    @staticmethod
    async def run(agent, input_text, *, max_turns):
        await asyncio.sleep(0.05)


class AgentExecutionServiceTest(SimpleTestCase):
    def test_runs_tool_chain_and_builds_report(self):
        """
        シナリオ:
        - 入力: Function Toolを1つ登録したAgentとユーザーの依頼。
        - 処理: Runnerへ依頼を渡し、返されたTool Call/Resultを実行履歴へ変換する。
        - 期待値: Tool履歴、最終出力、ターン数、上限ターン数が構造化される。
        """
        service = AgentExecutionService(
            name="Test Agent",
            instructions="Use the available tools.",
            tools=[lookup_skill],
            runner=FakeRunner,
        )

        run = service.run_sync("調べて", max_turns=4)

        self.assertIs(run.status, AgentRunStatus.COMPLETED)
        self.assertEqual(FakeRunner.received_input, "調べて")
        self.assertEqual(FakeRunner.received_max_turns, 4)
        self.assertEqual(FakeRunner.received_agent.tools[0].name, "lookup_skill")
        self.assertEqual(run.tool_calls[0].arguments, {"topic": "science"})
        self.assertEqual(run.tool_results[0].output, "result:science")
        self.assertEqual(run.report.output, "最終レポート")
        self.assertEqual(run.report.turns, 2)
        self.assertEqual(run.to_dict()["status"], "completed")

    def test_returns_failed_run_when_runner_fails(self):
        """
        シナリオ:
        - 入力: Runnerがプロバイダー障害を返すAgent依頼。
        - 処理: 実行サービスが例外を捕捉して失敗レポートを作成する。
        - 期待値: 例外を外へ漏らさず、FAILEDとエラー内容を返す。
        """
        service = AgentExecutionService(
            name="Test Agent",
            instructions="Use the available tools.",
            runner=FailingRunner,
        )

        run = service.run_sync("実行")

        self.assertIs(run.status, AgentRunStatus.FAILED)
        self.assertEqual(run.report.error, "provider unavailable")
        self.assertIsNone(run.report.output)

    def test_streams_tool_selected_and_completed_before_final_report(self):
        """
        シナリオ:
        - 入力: ストリーミング対応RunnerへAgentを実行する。
        - 処理: Tool選択、Tool結果、最終レポートの順に意味イベントを返す。
        - 期待値: 最終レポートを待たずTool完了イベントを受信できる。
        """
        service = AgentExecutionService(
            name="Streaming Agent",
            instructions="Use the available tools.",
            tools=[lookup_skill],
            runner=StreamingRunner,
        )

        async def collect_events():
            return [event async for event in service.stream("実行")]

        events = asyncio.run(collect_events())

        self.assertEqual(
            [event["type"] for event in events],
            ["run.started", "tool.selected", "tool.completed", "report.completed"],
        )
        self.assertEqual(events[1]["arguments"], {"topic": "science"})
        self.assertEqual(events[2]["sequence"], 1)
        self.assertEqual(events[2]["output"], "result:science")
        self.assertEqual(events[-1]["run"].report.output, "ストリーミング最終レポート")

    def test_returns_timed_out_run_when_runner_exceeds_limit(self):
        """
        シナリオ:
        - 入力: 指定時間内に完了しないRunner。
        - 処理: asyncio.wait_forでAgent実行を制限する。
        - 期待値: TIMED_OUTとタイムアウト理由を返す。
        """
        service = AgentExecutionService(
            name="Test Agent",
            instructions="Use the available tools.",
            runner=SlowRunner,
        )

        run = service.run_sync("実行", timeout_seconds=0.001)

        self.assertIs(run.status, AgentRunStatus.TIMED_OUT)
        self.assertEqual(run.report.error, "Agent実行がタイムアウトしました")

    def test_preserves_partial_tool_trace_when_stream_fails(self):
        """
        シナリオ:
        - 入力: Tool選択イベントの後でストリームが失敗するRunner。
        - 処理: 失敗したストリームから実行済みToolの履歴を復元する。
        - 期待値: FAILEDでも、途中までのTool CallがAgentRunに残る。
        """
        service = AgentExecutionService(
            name="Streaming Agent",
            instructions="Use the available tools.",
            tools=[lookup_skill],
            runner=FailingStreamingRunner,
        )

        async def collect_events():
            return [event async for event in service.stream("実行")]

        events = asyncio.run(collect_events())

        self.assertIs(events[-1]["run"].status, AgentRunStatus.FAILED)
        self.assertEqual(events[-1]["run"].tool_calls[0].name, "lookup_skill")

    def test_rejects_invalid_execution_limits(self):
        """
        シナリオ:
        - 入力: 空入力または0以下の上限ターン数。
        - 処理: Runnerを呼ぶ前に実行条件を検証する。
        - 期待値: 不正な依頼はValueErrorとして拒否される。
        """
        service = AgentExecutionService(
            name="Test Agent",
            instructions="Use the available tools.",
            runner=FakeRunner,
        )

        with self.assertRaises(ValueError) as empty_input:
            service.run_sync("", max_turns=1)
        self.assertEqual(str(empty_input.exception), "input_text must not be empty")

        with self.assertRaises(ValueError) as invalid_max_turns:
            service.run_sync("実行", max_turns=0)
        self.assertEqual(
            str(invalid_max_turns.exception), "max_turns must be greater than zero"
        )
