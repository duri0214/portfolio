from datetime import datetime

from ai_agent.models import Message, Entity


class ConversationService:
    @staticmethod
    def get_next_entity(input_text):
        """
        Determine the next entity to respond based on speed and response ability.

        Args:
            input_text (str): The input text to consider for response.

        Returns:
            Entity: The next entity to respond.

        Raises:
            ValueError: If no entity is able to respond.
        """
        entities = list(Entity.objects.all().order_by("-speed"))
        if not entities:
            raise ValueError("No entities available")

        for entity in entities:
            if entity.think(input_text):
                return entity

        raise ValueError("No entity is able to respond")

    @staticmethod
    def create_message(entity, content):
        """
        Create a new message for the given entity.
        """
        return Message.objects.create(
            entity=entity,
            message_content=content,
            created_at=datetime.now(),
        )
