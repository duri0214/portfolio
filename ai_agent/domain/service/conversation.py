from ai_agent.domain.repository.conversation import ConversationRepository
from ai_agent.domain.valueobject.conversation import EntityVO


class ConversationService:
    @staticmethod
    def initialize_timeline():
        """
        Initialize the timeline by assigning first turn values based on entity speed.
        """
        entities = ConversationRepository.get_all_entities()
        for entity in entities:
            ConversationRepository.update_or_create_action_timeline(
                entity=entity,
                defaults={"next_turn": 1 / entity.speed},
            )

    @staticmethod
    def get_next_entity():
        """
        Get the next entity to act based on the timeline.

        Returns:
            Entity: The next entity that should act.
        """
        timelines = ConversationRepository.get_timelines_ordered_by_next_turn()
        if not timelines.exists():
            raise ValueError("No entities available in the timeline.")

        next_action = timelines.first()

        # タイムラインを更新
        ConversationRepository.update_next_turn(
            action_timeline=next_action, increment=1 / next_action.entity.speed
        )

        return next_action.entity

    @staticmethod
    def create_message(entity, content):
        """
        Create a new message for the given entity.

        Args:
            entity (Entity): The entity creating the message.
            content (str): The content of the message.

        Returns:
            Message: The created message instance.
        """
        return ConversationRepository.create_message(entity=entity, content=content)

    @staticmethod
    def simulate_next_actions(max_steps=10) -> list[EntityVO]:
        """
        Simulates the next sequence of entity actions up to 'max_steps'.

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
            next_action = min(timelines, key=lambda t: t.next_turn)

            simulation.append(
                EntityVO(name=next_action.entity.name, next_turn=next_action.next_turn)
            )

            # 仮で次回行動予定を計算
            next_action.next_turn += 1 / next_action.entity.speed

        return simulation
