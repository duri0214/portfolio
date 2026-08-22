import asyncio
from datetime import datetime, timezone

from django.test import SimpleTestCase

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.game_agent import GameAgentService
from ai_agent.domain.service.skill_tools import GameToolSet, SkillToolCatalog
from ai_agent.domain.valueobject.agent_execution import (
    AgentRun,
    AgentRunStatus,
    Report,
    ToolCall,
    ToolResult,
)


class SkillToolCatalogTest(SimpleTestCase):
    def test_catalog_contains_display_names_and_implementation_names(self):
        """
        シナリオ:
        - 入力: SkillToolCatalogの定義一覧を取得する。
        - 処理: UI表示名とAgent登録名をそれぞれ抽出する。
        - 期待値: 6個のToolが重複なく対応付けられている。
        """
        definitions = SkillToolCatalog.definitions()

        self.assertEqual(len(definitions), 6)
        self.assertEqual(
            {definition.name for definition in definitions},
            {
                "analyze_reading",
                "analyze_expression",
                "calculate",
                "compare_quantities",
                "infer_cause",
                "analyze_observation",
            },
        )
        self.assertTrue(all(definition.display_name for definition in definitions))

    def test_game_tool_set_updates_state_for_direct_tool_calls(self):
        """
        シナリオ:
        - 入力: GameToolSetの計算Toolを呼び出す。
        - 処理: ToolアダプターがGameServiceへ構造化引数を渡す。
        - 期待値: 構造化結果が返り、GameToolSetの状態に効果が反映される。
        """
        tool_set = GameToolSet()

        result = tool_set.calculate("mondai-mathematics")

        self.assertTrue(result["success"])
        self.assertEqual(result["tool_name"], "calculate")
        self.assertEqual(tool_set.state.experience, 10)
        self.assertEqual(tool_set.state.mondai("mondai-mathematics").hit_points, 2)

    def test_game_tool_set_rejects_a_tool_target_outside_selected_problem(self):
        """
        シナリオ:
        - 入力: 国語の問題を選択した状態で、算数の問題IDをToolへ渡す。
        - 処理: GameToolSetのTool引数ガードレールで対象を検証する。
        - 期待値: 選択中の問題以外へのTool実行が拒否される。
        """
        state = GameService.select_mondai(GameService.create_game(), "mondai-language")
        tool_set = GameToolSet(state)

        with self.assertRaisesRegex(ValueError, "選択中の問題以外"):
            tool_set.calculate("mondai-mathematics")

    def test_function_tools_are_registered_without_fixed_chain_order(self):
        """
        シナリオ:
        - 入力: GameToolSetからAgent用Function Tool一覧を取得する。
        - 処理: 6個のSkill関数をSDKのFunction Toolへ変換する。
        - 期待値: Agentが全Toolを選択でき、特定の呼び出し順を強制しない。
        """
        tools = GameToolSet().function_tools()

        self.assertEqual(
            {tool.name for tool in tools},
            {definition.name for definition in SkillToolCatalog.definitions()},
        )
        self.assertEqual(len(tools), 6)

    def test_game_agent_registers_all_skill_tools(self):
        """
        シナリオ:
        - 入力: ゲーム用Agentサービスを生成する。
        - 処理: GameToolSetのFunction ToolをAgentへ登録する。
        - 期待値: Agentが6個すべてのSkill Toolを利用できる。
        """
        service = GameAgentService()

        self.assertEqual(
            {tool.name for tool in service.execution.agent.tools},
            {definition.name for definition in SkillToolCatalog.definitions()},
        )

    def test_preset_lines_have_evaluable_representative_tool_chains(self):
        """
        シナリオ:
        - 入力: 国語・算数・理科の問題と3種類のプリセットセリフ。
        - 処理: セリフごとの期待Chainを作り、同じTool CallをAgentRunへ詰めて評価する。
        - 期待値: 各代表ケースのTool順が期待値と一致すると判定できる。
        """
        cases = (
            ("mondai-language", "line-challenge"),
            ("mondai-mathematics", "line-observe"),
            ("mondai-science", "line-chain"),
        )
        now = datetime.now(timezone.utc)

        for mondai_id, line_id in cases:
            with self.subTest(mondai_id=mondai_id, line_id=line_id):
                state = GameService.select_line(
                    GameService.select_mondai(GameService.create_game(), mondai_id),
                    line_id,
                )
                expected = GameAgentService.expected_tool_chain(state)
                run = AgentRun(
                    run_id=f"run-{mondai_id}-{line_id}",
                    input_text="代表シナリオ",
                    max_turns=10,
                    status=AgentRunStatus.COMPLETED,
                    started_at=now,
                    completed_at=now,
                    tool_calls=tuple(
                        ToolCall(
                            call_id=f"call-{index}",
                            name=tool_name,
                            arguments={"target_mondai_id": mondai_id},
                            sequence=index,
                        )
                        for index, tool_name in enumerate(expected, start=1)
                    ),
                    tool_results=(),
                    report=Report(
                        output="代表ケース完了",
                        status=AgentRunStatus.COMPLETED,
                        tool_calls=(),
                        tool_results=(),
                        turns=1,
                    ),
                )

                evaluation = GameAgentService.evaluate_tool_chain(state, run)

                self.assertEqual(evaluation.expected, expected)
                self.assertTrue(evaluation.matched)

    def test_agent_run_becomes_explainable_execution_history(self):
        """
        シナリオ:
        - 入力: 横断問題に対するAgentのTool Call/Resultと最終説明。
        - 処理: AgentRunを画面用の実行記録へ変換し、Cookie形式で復元する。
        - 期待値: 選択理由、加工内容、入力、結果、状態変化が保持される。
        """
        state = GameService.select_line(
            GameService.select_mondai(
                GameService.create_game(), "mondai-language-mathematics"
            ),
            "line-observe",
        )
        now = datetime.now(timezone.utc)
        agent_output = "観察して条件を整理したため、計算Toolを選びました。" + (
            "詳細。" * 300
        )
        run = AgentRun(
            run_id="run-1",
            input_text="横断問題を観察して解く",
            max_turns=10,
            status=AgentRunStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            tool_calls=(
                ToolCall(
                    call_id="call-1",
                    name="calculate",
                    arguments={
                        "target_mondai_id": "mondai-language-mathematics",
                    },
                    sequence=1,
                ),
            ),
            tool_results=(
                ToolResult(
                    call_id="call-1",
                    name="calculate",
                    output={
                        "display_name": "計算",
                        "success": True,
                        "target_mondai_id": "mondai-language-mathematics",
                        "damage": 1,
                        "experience_gained": 10,
                        "mondai_remaining_hit_points": 2,
                        "message": "計算が成功し、国語×算数の問題に1ダメージ。",
                    },
                    succeeded=True,
                    sequence=1,
                ),
            ),
            report=Report(
                output=agent_output,
                status=AgentRunStatus.COMPLETED,
                tool_calls=(),
                tool_results=(),
                turns=1,
            ),
        )

        record = GameAgentService.create_execution_record(state, run)
        state_with_record = state.with_execution_record(record)
        restored = type(state).from_dict(state_with_record.to_dict())

        self.assertEqual(record.problem_subjects, "国語 × 算数")
        self.assertEqual(record.explanation, agent_output)
        self.assertEqual(record.steps[0].operation, "数値や式を計算して答えを確かめる")
        self.assertEqual(
            record.steps[0].input_summary,
            "対象: 国語×算数の問題",
        )
        self.assertEqual(
            record.steps[0].result_summary,
            "計算が成功し、国語×算数の問題に1ダメージ。",
        )
        self.assertEqual(restored.execution_history[0], record)
        self.assertEqual(restored.execution_history[0].agent_run, run)

    def test_stream_events_include_input_and_result_summaries(self):
        """
        シナリオ:
        - 入力: 選択済みの問題へ計算Toolを実行するストリームイベント。
        - 処理: ゲーム用Agentサービスがイベントへ画面表示用の要約を付加する。
        - 期待値: 選択・開始・完了イベントで入力、結果、実行順を追跡できる。
        """
        state = GameService.select_line(
            GameService.select_mondai(GameService.create_game(), "mondai-language"),
            "line-observe",
        )
        service = GameAgentService(tools=GameToolSet(state))

        async def fake_stream(_input_text, *, max_turns=10):
            yield {"type": "run.started", "run_id": "run-1"}
            yield {
                "type": "tool.selected",
                "call_id": "call-1",
                "tool_name": "calculate",
                "arguments": {"target_mondai_id": "mondai-language"},
                "sequence": 1,
            }
            yield {
                "type": "tool.completed",
                "call_id": "call-1",
                "tool_name": "calculate",
                "sequence": 1,
                "output": {"message": "計算が成功しました。"},
            }

        service.execution.stream = fake_stream

        async def collect_events():
            return [event async for event in service.stream_selected()]

        events = asyncio.run(collect_events())

        self.assertEqual(events[1]["input_summary"], "対象: 国語の問題")
        self.assertEqual(events[2]["input_summary"], "対象: 国語の問題")
        self.assertEqual(events[3]["result_summary"], "計算が成功しました。")
        self.assertEqual(events[3]["sequence"], 1)
