from django.test import SimpleTestCase

from ai_agent.domain.service.game import GameService
from ai_agent.domain.service.skill_tools import SkillToolCatalog
from ai_agent.domain.valueobject.game import BoardSpaceType, SkillCategory


class GameServiceTest(SimpleTestCase):
    def test_create_game_has_six_problems_and_preset_lines(self):
        """
        シナリオ:
        - 入力: 新規ゲーム作成の依頼。
        - 処理: GameService.create_gameを呼び出す。
        - 期待値: 3x3盤面に単一教科と科目横断の6つの問題、プリセットセリフが作られる。
        """
        state = GameService.create_game()

        self.assertEqual(state.board_size, 3)
        self.assertEqual(len(state.mondais), 6)
        self.assertEqual(
            {mondai.category for mondai in state.mondais},
            {SkillCategory.LANGUAGE, SkillCategory.MATHEMATICS, SkillCategory.SCIENCE},
        )
        self.assertEqual(
            {
                mondai.category_display_name
                for mondai in state.mondais
                if len(mondai.categories) == 2
            },
            {"国語 × 算数", "国語 × 理科", "算数 × 理科"},
        )
        self.assertEqual(len(state.preset_lines), 3)
        self.assertEqual(
            {line.label for line in state.preset_lines},
            {"直接解決を試す", "条件を整理して解く", "別の観点で検証する"},
        )
        self.assertEqual(state.experience, 0)

    def test_selecting_problem_moves_player_to_problem_position(self):
        """
        シナリオ:
        - 入力: 初期盤面で国語の問題駒を選択する。
        - 処理: GameServiceが対象問題を選び、プレイヤー位置を更新する。
        - 期待値: プレイヤーが国語の問題と同じマスへ移動する。
        """
        state = GameService.create_game()
        state = state.with_selection(line_id="line-observe")

        next_state = GameService.select_mondai(state, "mondai-language")

        self.assertEqual(next_state.selected_mondai_id, "mondai-language")
        self.assertIsNone(next_state.selected_line_id)
        self.assertEqual(
            next_state.player_position,
            next_state.mondai("mondai-language").position,
        )
        self.assertNotEqual(state.player_position, next_state.player_position)
        restored_state = type(next_state).from_dict(next_state.to_dict())
        self.assertEqual(restored_state.player_position, next_state.player_position)

    def test_create_game_defines_bonus_and_rest_spaces_for_empty_cells(self):
        """
        シナリオ:
        - 入力: 新規ゲームの3x3盤面。
        - 処理: 問題以外の盤面マス定義を確認する。
        - 期待値: 右中央に経験値ボーナス、左下に休憩が配置される。
        """
        state = GameService.create_game()

        self.assertEqual(len(state.board_spaces), 2)
        self.assertEqual(
            {space.space_type for space in state.board_spaces},
            {BoardSpaceType.EXPERIENCE_BONUS, BoardSpaceType.REST},
        )
        self.assertEqual(
            {
                (space.position.row, space.position.column)
                for space in state.board_spaces
            },
            {(1, 2), (2, 0)},
        )

    def test_selecting_bonus_space_grants_experience_and_records_event_once(self):
        """
        シナリオ:
        - 入力: 問題を選択した状態で、未使用の経験値ボーナスへ移動する。
        - 処理: GameService.select_board_spaceを呼び出し、状態を保存・復元する。
        - 期待値: 選択が解除され、経験値+10と盤面イベント履歴が残り、再利用は拒否される。
        """
        state = GameService.create_game().with_selection(
            mondai_id="mondai-language",
            line_id="line-observe",
        )

        next_state = GameService.select_board_space(state, "board-space-bonus")

        self.assertEqual(
            next_state.player_position,
            next_state.board_space("board-space-bonus").position,
        )
        self.assertEqual(next_state.experience, 10)
        self.assertIsNone(next_state.selected_mondai_id)
        self.assertIsNone(next_state.selected_line_id)
        self.assertEqual(next_state.used_board_space_ids, ("board-space-bonus",))
        self.assertEqual(next_state.board_event_history[0].experience_gained, 10)
        restored_state = type(next_state).from_dict(next_state.to_dict())
        self.assertEqual(
            restored_state.used_board_space_ids,
            next_state.used_board_space_ids,
        )
        self.assertEqual(
            restored_state.board_event_history,
            next_state.board_event_history,
        )

        with self.assertRaisesRegex(ValueError, "already used"):
            GameService.select_board_space(next_state, "board-space-bonus")

    def test_selecting_rest_space_recovers_damaged_unsolved_problems(self):
        """
        シナリオ:
        - 入力: 読解Skillで国語の問題HPを2へ減らしたゲーム状態。
        - 処理: 休憩マスへ移動して一度だけ回復効果を適用する。
        - 期待値: 国語の問題だけが1HP回復し、経験値と盤面イベントに反映される。
        """
        state, _ = GameService.execute_skill(
            GameService.create_game(),
            SkillToolCatalog.get("analyze_reading"),
            target_mondai_id="mondai-language",
        )

        next_state = GameService.select_board_space(state, "board-space-rest")

        self.assertEqual(next_state.mondai("mondai-language").hit_points, 3)
        self.assertEqual(next_state.mondai("mondai-mathematics").hit_points, 3)
        self.assertEqual(next_state.experience, 10)
        event = next_state.board_event_history[0]
        self.assertEqual(event.recovered_hit_points, 1)
        self.assertEqual(event.recovered_problem_count, 1)

    def test_successful_skill_returns_new_state_and_effect(self):
        """
        シナリオ:
        - 入力: 国語の問題を対象に読解分析を実行する。
        - 処理: GameServiceがSkill結果を適用する。
        - 期待値: 問題HP、経験値、Tool履歴が更新され、元の状態は変わらない。
        """
        state = GameService.select_mondai(GameService.create_game(), "mondai-language")
        definition = SkillToolCatalog.get("analyze_reading")

        next_state, result = GameService.execute_skill(
            state,
            definition,
            target_mondai_id="mondai-language",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.damage, 1)
        self.assertEqual(result.experience_gained, 10)
        self.assertEqual(next_state.mondai("mondai-language").hit_points, 2)
        self.assertEqual(next_state.experience, 10)
        self.assertEqual(next_state.tool_history, ("analyze_reading",))
        self.assertEqual(state.mondai("mondai-language").hit_points, 3)

    def test_skill_targets_selected_cross_subject_problem(self):
        """
        シナリオ:
        - 入力: 国語×算数または国語×理科の問題を選択し、別問題のIDを持つSkill入力。
        - 処理: GameServiceが選択中の問題へSkillを適用する。
        - 期待値: 選択中の科目横断問題のHPだけが減少し、入力された別問題は変化しない。
        """
        for selected_mondai_id in (
            "mondai-language-mathematics",
            "mondai-language-science",
        ):
            with self.subTest(selected_mondai_id=selected_mondai_id):
                state = GameService.select_mondai(
                    GameService.create_game(), selected_mondai_id
                )

                next_state, result = GameService.execute_skill(
                    state,
                    SkillToolCatalog.get("analyze_reading"),
                    target_mondai_id="mondai-language",
                )

                self.assertTrue(result.success)
                self.assertEqual(result.target_mondai_id, selected_mondai_id)
                self.assertEqual(next_state.mondai(selected_mondai_id).hit_points, 2)
                self.assertEqual(next_state.mondai("mondai-language").hit_points, 3)

    def test_skill_damage_does_not_exceed_remaining_hit_points(self):
        state = GameService.create_game()
        state, _ = GameService.execute_skill(
            state,
            SkillToolCatalog.get("analyze_expression"),
            target_mondai_id="mondai-language",
        )
        state = state.with_selection(mondai_id="mondai-language")

        state, result = GameService.execute_skill(
            state,
            SkillToolCatalog.get("analyze_expression"),
            target_mondai_id="mondai-language",
        )

        self.assertEqual(result.damage, 1)
        self.assertEqual(result.mondai_remaining_hit_points, 0)
        self.assertTrue(state.mondai("mondai-language").solved)

    def test_failed_skill_has_no_mondai_effect(self):
        """
        シナリオ:
        - 入力: 解決済みの算数の問題を対象に計算を実行する。
        - 処理: 解決後のSkillを適用する。
        - 期待値: 失敗結果になり、問題の状態は変わらない。
        """
        state = GameService.create_game()
        definition = SkillToolCatalog.get("calculate")
        for _ in range(3):
            state, _ = GameService.execute_skill(
                state,
                definition,
                target_mondai_id="mondai-mathematics",
            )

        next_state, result = GameService.execute_skill(
            state,
            definition,
            target_mondai_id="mondai-mathematics",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.damage, 0)
        self.assertEqual(next_state.mondai("mondai-mathematics").hit_points, 0)
        self.assertEqual(next_state.experience, 30)
        self.assertEqual(next_state.tool_history, ("calculate",) * 4)

    def test_solved_problem_cannot_be_selected_for_a_line(self):
        state = GameService.create_game().with_selection(mondai_id="mondai-language")
        for _ in range(2):
            state, _ = GameService.execute_skill(
                state,
                SkillToolCatalog.get("analyze_expression"),
                target_mondai_id="mondai-language",
            )

        with self.assertRaisesRegex(ValueError, "already solved"):
            GameService.select_line(state, "line-challenge")

    def test_skill_chain_can_choose_two_tools_without_fixed_order(self):
        """
        シナリオ:
        - 入力: 国語の問題へ表現分析、続けて読解分析を実行する。
        - 処理: Agentが選択した順で2つのSkill結果を状態へ適用する。
        - 期待値: 2つのTool履歴、合計経験値25、問題HP0が得られる。
        """
        state = GameService.create_game()
        for tool_name in ("analyze_expression", "analyze_reading"):
            state, result = GameService.execute_skill(
                state,
                SkillToolCatalog.get(tool_name),
                target_mondai_id="mondai-language",
            )
            self.assertTrue(result.success)

        self.assertEqual(state.tool_history, ("analyze_expression", "analyze_reading"))
        self.assertEqual(state.experience, 25)
        self.assertTrue(state.mondai("mondai-language").solved)

    def test_skill_can_target_another_category(self):
        """
        シナリオ:
        - 入力: 国語の問題を対象に算数の計算Toolを実行する。
        - 処理: Agentが選んだ教科の異なるSkillを適用する。
        - 期待値: Skillが成功し、対象問題のHPと経験値が更新される。
        """
        state, result = GameService.execute_skill(
            GameService.create_game(),
            SkillToolCatalog.get("calculate"),
            target_mondai_id="mondai-language",
        )

        self.assertTrue(result.success)
        self.assertEqual(state.mondai("mondai-language").hit_points, 2)
        self.assertEqual(state.experience, 10)
