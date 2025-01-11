from datetime import datetime

from ai_agent.models import Message, Entity, ActionTimeline


class ConversationService:
    @staticmethod
    def initialize_timeline():
        """
        Initialize the timeline by assigning first turn values based on entity speed.
        """
        entities = Entity.objects.all()
        for entity in entities:
            # 初期の next_turn をエンティティの速度に基づいて設定
            ActionTimeline.objects.update_or_create(
                entity=entity, defaults={"next_turn": 1 / entity.speed}
            )

    @staticmethod
    def get_next_entity():
        """
        Get the next entity to act based on the timeline.

        Returns:
            Entity: The next entity that should act.
        """
        # 次に行動するエンティティを取得
        timelines = ActionTimeline.objects.order_by("next_turn")
        if not timelines.exists():
            raise ValueError("No entities available in the timeline.")

        # 次に行動するエンティティを取得
        next_action = timelines.first()

        # タイムライン更新: 次回行動予定ターンを計算
        next_action.next_turn += 1 / next_action.entity.speed
        next_action.save()

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
        # メッセージを作成
        message = Message.objects.create(
            entity=entity,
            message_content=content,
            created_at=datetime.now(),
        )

        return message

    @staticmethod
    def simulate_next_actions(max_steps=10):
        """
        Simulates the next sequence of entity actions up to 'max_steps'.

        Args:
            max_steps (int): How many actions to simulate.

        Returns:
            List[Tuple[str, float]]: A list of tuples containing the entity's name and the turn when they act.
        """
        timelines = list(ActionTimeline.objects.all().order_by("next_turn"))
        if not timelines:
            raise ValueError("No entities available in the timeline.")

        simulation = []
        for _ in range(max_steps):
            # 次に行動するエンティティを選択
            next_action = min(timelines, key=lambda t: t.next_turn)
            simulation.append((next_action.entity.name, next_action.next_turn))

            # 仮で次回行動予定を計算
            next_action.next_turn += 1 / next_action.entity.speed

        return simulation
