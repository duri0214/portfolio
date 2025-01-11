from django.test import TestCase

from ai_agent.domain.service.conversation import ConversationService
from ai_agent.models import Entity, ActionTimeline


class ConversationServiceTest(TestCase):
    def setUp(self):
        """
        Set up entities and initialize timeline for testing.
        """
        self.entity1 = Entity.objects.create(name="Entity1", speed=100)  # 高速
        self.entity2 = Entity.objects.create(name="Entity2", speed=10)  # 低速

        # 初期化時にタイムラインを設定
        ConversationService.initialize_timeline()

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
        next_entity = ConversationService.get_next_entity()
        self.assertEqual(next_entity, self.entity1)

        # Entity1 が次回行動予定を早く更新するため、2回目も Entity1 が選ばれる
        next_entity = ConversationService.get_next_entity()
        self.assertEqual(next_entity, self.entity1)

        # 速度の差が 10 倍であるため、Entity1 が 8 回行動した後に Entity2 のターンが来る
        for _ in range(9):
            next_entity = ConversationService.get_next_entity()
        self.assertEqual(next_entity, self.entity2)

        # Entity2 が行動した次には再び高速な Entity1 の順番となる
        next_entity = ConversationService.get_next_entity()
        self.assertEqual(next_entity, self.entity1)
