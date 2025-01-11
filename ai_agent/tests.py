from django.test import TestCase

from ai_agent.domain.service.conversation import ConversationService
from ai_agent.models import Entity


class ConversationServiceTest(TestCase):
    def setUp(self):
        """
        セットアップメソッドでテストデータを準備します。
        """
        self.entity1 = Entity.objects.create(name="Entity1", speed=20, forbidden_keywords="ng words")
        self.entity2 = Entity.objects.create(name="Entity2", speed=10)

    def test_get_next_entity(self):
        """
        禁止キーワードを含まない場合、Speedが高いエンティティが選ばれるかテストします。
        """
        input_text = "This is a test without any problematic content"

        # 次のエンティティを取得
        next_entity = ConversationService.get_next_entity(input_text)

        # Speedが高いエンティティ (entity1) が選ばれるはず
        self.assertEqual(next_entity, self.entity1)

    def test_get_next_entity_with_forbidden_keyword(self):
        """
        禁止されたキーワードを含む場合、エンティティが回答できないことをテストします。
        """
        input_text = "This text contains ng words"

        # 次のエンティティを取得
        next_entity = ConversationService.get_next_entity(input_text)

        # entity1 は禁止キーワードのため選ばれず、entity2 が選ばれるはず
        self.assertEqual(next_entity, self.entity2)
