from datetime import datetime

from ai_agent.models import Entity, ActionTimeline, Message


class ConversationRepository:
    @staticmethod
    def get_all_entities():
        return Entity.objects.all()

    @staticmethod
    def get_timelines_ordered_by_next_turn():
        return ActionTimeline.objects.order_by("next_turn")

    @staticmethod
    def update_or_create_action_timeline(entity, defaults):
        return ActionTimeline.objects.update_or_create(entity=entity, defaults=defaults)

    @staticmethod
    def update_next_turn(action_timeline, increment):
        action_timeline.next_turn += increment
        action_timeline.save()

    @staticmethod
    def create_message(entity, content):
        return Message.objects.create(
            entity=entity,
            message_content=content,
            created_at=datetime.now(),
        )
