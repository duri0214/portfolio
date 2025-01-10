from django.test import TestCase

from ai_agent.domain.service.conversation import ConversationService
from ai_agent.models import Entity


class ConversationServiceTest(TestCase):
    def setUp(self):
        """
        セットアップメソッドでテストデータを準備します。
        """
        self.entity1 = Entity.objects.create(name="Entity1", speed=10, forbidden_keywords="forbidden")
        self.entity2 = Entity.objects.create(name="Entity2", speed=20)

    def test_get_next_entity(self):
        """
        次のエンティティが正しく選ばれるかテストします。
        """
        input_text = "This is a test without forbidden words"

        # 次のエンティティを取得
        next_entity = ConversationService.get_next_entity(input_text)

        # Speedが高いエンティティが選ばれるはず
        self.assertEqual(next_entity, self.entity2)

    def test_get_next_entity_with_forbidden_keyword(self):
        """
        禁止されたキーワードを含む場合、エンティティが回答できないことをテストします。
        """
        input_text = "This text contains forbidden words"

        # 次のエンティティを取得
        next_entity = ConversationService.get_next_entity(input_text)

        # entity1 は forbidden キーワードを含んでいるので entity2 が選ばれるはず
        self.assertEqual(next_entity, self.entity2)
