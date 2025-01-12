from ai_agent.domain.repository.conversation import ConversationRepository
from ai_agent.domain.service.googlemaps_review import GoogleMapsReviewService
from ai_agent.domain.service.ng_word import NGWordService
from ai_agent.domain.service.rag import RagService
from ai_agent.domain.valueobject.conversation import EntityVO
from ai_agent.models import Entity, ActionHistory


class ConversationService:
    @staticmethod
    def calculate_next_turn_increment(speed: float) -> float:
        """
        Calculate the increment for next_turn based on entity speed.
        This ensures consistency in how the increment is derived, and makes future
        adjustments easier.
        """
        return 1 / speed

    @staticmethod
    def initialize_timeline():
        """
        Initialize the timeline by assigning first turn values based on entity speed.
        """
        entities = ConversationRepository.get_all_entities()
        for entity in entities:
            ConversationRepository.update_or_create_action_timeline(
                entity=entity,
                defaults={
                    "next_turn": ConversationService.calculate_next_turn_increment(
                        entity.speed
                    )
                },
            )

    @staticmethod
    def get_next_entity(input_text: str):
        """
        Get the next entity to act based on the timeline, considering
        its ability to act (`can_act`) determined by `think`.

        Args:
            input_text (str): The input text for the entity's `think` process.

        Returns:
            Entity: The next entity that should act.

        Raises:
            ValueError: If no entities are available to act.
        """
        timelines = ConversationRepository.get_timelines_ordered_by_next_turn()
        if not timelines.exists():
            raise ValueError("No entities available in the timeline.")

        candidates = []
        for timeline in timelines:
            timeline.can_act = ConversationService.think(timeline.entity, input_text)
            timeline.save()
            if timeline.can_act:
                candidates.append(timeline)

        # 次の行動順 (next_turn) 最小値のエンティティを選択する
        if candidates:
            next_action = min(candidates, key=lambda t: t.next_turn)
            ConversationRepository.update_next_turn(
                action_timeline=next_action,
                increment=ConversationService.calculate_next_turn_increment(
                    next_action.entity.speed
                ),
            )
            return next_action.entity

        # このターンでは発言可能なエンティティがいない場合、すべてのエンティティの next_turn を更新して次のターンへ進む
        for timeline in timelines:
            ConversationRepository.update_next_turn(
                action_timeline=timeline,
                increment=ConversationService.calculate_next_turn_increment(
                    timeline.entity.speed
                ),
            )
        raise ValueError("No entities are available to act in this turn.")

    @staticmethod
    def simulate_next_actions(max_steps=10) -> list[EntityVO]:
        """
        Simulates the next sequence of entity actions up to 'max_steps'
        and creates ActionHistory records for each action.

        Args:
            max_steps (int): How many actions to simulate.

        Returns:
            List[EntityVO]: A list of EntityVO objects containing the entity's name and the turn when they act.
        """
        timelines = list(ConversationRepository.get_timelines_ordered_by_next_turn())
        if not timelines:
            raise ValueError("No entities available in the timeline.")

        simulation = []
        for _ in range(max_steps):
            # 次の行動を決定 (next_turn が最小のタイムラインを選ぶ)
            next_action = min(timelines, key=lambda t: t.next_turn)

            # ActionHistory レコードを作成
            ActionHistory.objects.create(
                entity=next_action.entity,
                acted_at_turn=int(next_action.next_turn),
                done=False,  # 行動前なので未完了
            )

            # シミュレーションの結果を保存
            simulation.append(
                EntityVO(name=next_action.entity.name, next_turn=next_action.next_turn)
            )

            # 次の行動予定を仮で計算
            next_action.next_turn += 1 / next_action.entity.speed

        return simulation

    @staticmethod
    def think(entity: Entity, input_text: str):
        """
        Process the entity's thought logic to determine if it can respond.

        Args:
            entity (Entity): The entity performing the thought process.
            input_text (str): The input text to evaluate.

        Returns:
            bool: True if the entity can respond, False otherwise.
        """
        if entity.thinking_type == "google_maps_based":
            return GoogleMapsReviewService.can_respond(input_text, entity)

        elif entity.thinking_type == "rag_based":
            return RagService.can_respond(input_text, entity)

        elif entity.thinking_type == "ng_word_based":
            return NGWordService.can_respond(input_text, entity)

        # デフォルトで発言可能
        return True
