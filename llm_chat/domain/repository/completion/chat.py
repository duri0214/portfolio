from django.contrib.auth.models import User

from llm_chat.domain.valueobject.completion.message import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    @staticmethod
    def find_chat_history(user: User) -> list[MessageDTO]:
        chat_logs = ChatLogs.objects.filter(user=user).order_by("created_at")
        return [chat_log.to_message_dto() for chat_log in chat_logs]

    @staticmethod
    def insert(message: MessageDTO):
        message.to_entity().save()

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])
