from unittest.mock import patch

from django.test import TestCase

from ai_agent.domain.repository.conversation import ConversationRepository
from ai_agent.domain.service.conversation import ConversationService
from ai_agent.domain.valueobject.conversation import EntityVO
from ai_agent.models import Entity, ActionTimeline


class ConversationServiceTest(TestCase):
    def setUp(self):
        """
        Set up entities and initialize the timeline for testing.
        """
        # Entity1: 高速で Google Maps レビューに基づくタイプ
        self.entity1 = Entity.objects.create(
            name="Entity1",
            speed=100,  # 高速
            thinking_type="google_maps_based",
        )
        # Entity2: 低速で NG ワードに基づくタイプ
        self.entity2 = Entity.objects.create(
            name="Entity2",
            speed=10,  # 低速
            thinking_type="ng_word_based",
        )

        # 初期化時にタイムラインを設定
        ConversationService.initialize_timeline()

        # テスト用の入力テキスト
        self.test_input_text = "sample input text"

    def test_timeline_initialization(self):
        """
        Test if the timeline is initialized correctly with all entities.
        """
        # タイムラインに全エンティティが登録されているか確認
        timelines = ActionTimeline.objects.all()
        self.assertEqual(timelines.count(), 2)

        # 各エンティティの next_turn が適切に計算されているか確認
        for timeline in timelines:
            self.assertEqual(timeline.next_turn, 1 / timeline.entity.speed)

    def test_action_order_based_on_speed(self):
        """
        Test action order based on entity speed.
        """
        # 最初に行動するのは高速な Entity1 のはず
        next_entity = ConversationService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

        # Entity1 が次回行動予定を早く更新するため、2回目も Entity1 が選ばれる
        next_entity = ConversationService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

        # 速度の差が 10 倍であるため、Entity1 が 8 回行動した後に Entity2 のターンが来る
        for _ in range(9):
            next_entity = ConversationService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity2)

        # Entity2 が行動した次には再び高速な Entity1 の順番となる
        next_entity = ConversationService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

    def test_create_message_updates_timeline(self):
        """
        Test if creating a message updates the timeline properly for the entity.
        """
        # Entity1 でメッセージを作成
        ConversationRepository.create_message(self.entity1, "Test Message")

        # タイムラインを確認
        timeline = ActionTimeline.objects.get(entity=self.entity1)

        # タイムライン初期化時の next_turn を確認
        self.assertEqual(timeline.next_turn, 1 / self.entity1.speed)

        # get_next_entity を1回実行すると next_turn が更新される
        ConversationService.get_next_entity(self.test_input_text)
        timeline.refresh_from_db()  # タイムラインを再取得
        self.assertEqual(
            timeline.next_turn, 1 / self.entity1.speed + 1 / self.entity1.speed
        )

    def test_simulate_next_actions(self):
        """
        Test if the simulate_next_actions function correctly predicts the next actions.
        """
        simulation = ConversationService.simulate_next_actions(max_steps=11)

        # シミュレーション結果の期待値
        expected_simulation = [
            EntityVO(name="Entity1", next_turn=0.01),
            EntityVO(name="Entity1", next_turn=0.02),
            EntityVO(name="Entity1", next_turn=0.03),
            EntityVO(name="Entity1", next_turn=0.04),
            EntityVO(name="Entity1", next_turn=0.05),
            EntityVO(name="Entity1", next_turn=0.06),
            EntityVO(name="Entity1", next_turn=0.07),
            EntityVO(name="Entity1", next_turn=0.08),
            EntityVO(name="Entity1", next_turn=0.09),
            EntityVO(name="Entity1", next_turn=0.10),
            EntityVO(name="Entity2", next_turn=0.10),
        ]
        # リスト全体を比較
        for actual, expected in zip(simulation, expected_simulation):
            self.assertEqual(actual.name, expected.name)
            self.assertAlmostEqual(actual.next_turn, expected.next_turn, places=2)

    @patch("ai_agent.domain.service.conversation.ConversationService.think")
    def test_can_act_false_skips_entity(self, mock_think):
        """
        Test if an entity is skipped when can_act is False.
        """

        # think をモック化して、Entity1 が always False を返すように設定
        def mock_think_side_effect(entity, input_text):
            if entity == self.entity1:
                return False  # Entity1 をパスさせる
            return True  # 他のエンティティは True を返す

        mock_think.side_effect = mock_think_side_effect

        # Entity1 は skip され、Entity2 が選ばれるはず
        next_entity = ConversationService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity2)

        # Entity2 が選ばれた後、next_turn が次のターン（0.2）になることを確認する
        timeline_entity2 = ActionTimeline.objects.get(entity=self.entity2)
        self.assertEqual(timeline_entity2.next_turn, 0.2)

        # モックが期待通り呼び出されたことを確認
        mock_think.assert_any_call(self.entity1, self.test_input_text)
        mock_think.assert_any_call(self.entity2, self.test_input_text)
