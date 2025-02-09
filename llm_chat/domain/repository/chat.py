from django.contrib.auth.models import User
from django.db.models import QuerySet

from llm_chat.domain.valueobject.chat import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    def __init__(self):
        pass

    @staticmethod
    def find_chat_history(user: User) -> QuerySet:
        return ChatLogs.objects.filter(user=user)

    @staticmethod
    def insert(message: MessageDTO):
        ChatLogs.objects.create(
            user=message.user, role=message.role.value, content=message.content
        )

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])
