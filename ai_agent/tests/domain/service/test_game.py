from django.test import SimpleTestCase

from ai_agent.domain.service.game import GameDomainError, GameService
from ai_agent.domain.service.skill_tools import SkillToolCatalog
from ai_agent.domain.valueobject.game import SkillCategory


class GameServiceTest(SimpleTestCase):
    def test_create_game_has_three_enemies_and_preset_lines(self):
        """
        シナリオ:
        - 入力: 新規ゲーム作成の依頼。
        - 処理: GameService.create_gameを呼び出す。
        - 期待値: 3x3盤面に国語・算数・理科の敵とプリセットセリフが作られる。
        """
        state = GameService.create_game()

        self.assertEqual(state.board_size, 3)
        self.assertEqual(
            {enemy.category for enemy in state.enemies},
            {SkillCategory.LANGUAGE, SkillCategory.MATHEMATICS, SkillCategory.SCIENCE},
        )
        self.assertEqual(len(state.preset_lines), 3)
        self.assertEqual(state.experience, 0)

    def test_successful_skill_returns_new_state_and_effect(self):
        """
        シナリオ:
        - 入力: 国語の敵を対象に読解分析をscore 80で実行する。
        - 処理: GameServiceがSkill結果を適用する。
        - 期待値: 敵HP、経験値、Tool履歴が更新され、元の状態は変わらない。
        """
        state = GameService.select_enemy(GameService.create_game(), "enemy-language")
        definition = SkillToolCatalog.get("analyze_reading")

        next_state, result = GameService.execute_skill(
            state,
            definition,
            target_enemy_id="enemy-language",
            score=80,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.damage, 1)
        self.assertEqual(result.experience_gained, 10)
        self.assertEqual(next_state.enemy("enemy-language").hit_points, 2)
        self.assertEqual(next_state.experience, 10)
        self.assertEqual(next_state.tool_history, ("analyze_reading",))
        self.assertEqual(state.enemy("enemy-language").hit_points, 3)

    def test_failed_skill_has_no_enemy_effect(self):
        """
        シナリオ:
        - 入力: 算数の敵を対象に計算をscore 40で実行する。
        - 処理: 成功基準未達のSkillを適用する。
        - 期待値: 失敗結果になり、敵HPと経験値は変わらない。
        """
        state = GameService.create_game()
        definition = SkillToolCatalog.get("calculate")

        next_state, result = GameService.execute_skill(
            state,
            definition,
            target_enemy_id="enemy-mathematics",
            score=40,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.damage, 0)
        self.assertEqual(next_state.enemy("enemy-mathematics").hit_points, 3)
        self.assertEqual(next_state.experience, 0)
        self.assertEqual(next_state.tool_history, ("calculate",))

    def test_skill_chain_can_choose_two_tools_without_fixed_order(self):
        """
        シナリオ:
        - 入力: 国語の敵へ表現分析、続けて読解分析をscore 80で実行する。
        - 処理: Agentが選択した順で2つのSkill結果を状態へ適用する。
        - 期待値: 2つのTool履歴、合計経験値25、敵HP0が得られる。
        """
        state = GameService.create_game()
        for tool_name in ("analyze_expression", "analyze_reading"):
            state, result = GameService.execute_skill(
                state,
                SkillToolCatalog.get(tool_name),
                target_enemy_id="enemy-language",
                score=80,
            )
            self.assertTrue(result.success)

        self.assertEqual(state.tool_history, ("analyze_expression", "analyze_reading"))
        self.assertEqual(state.experience, 25)
        self.assertTrue(state.enemy("enemy-language").defeated)

    def test_skill_cannot_target_another_category(self):
        """
        シナリオ:
        - 入力: 国語の読解分析を理科の敵へ向ける。
        - 処理: GameServiceが教科と敵の不一致を検証する。
        - 期待値: ドメインエラーが発生し、誤った効果が適用されない。
        """
        with self.assertRaises(GameDomainError):
            GameService.execute_skill(
                GameService.create_game(),
                SkillToolCatalog.get("analyze_reading"),
                target_enemy_id="enemy-science",
                score=100,
            )
