from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.valueobject.chat import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    @staticmethod
    def find_chat_history(user: User) -> list[MessageDTO]:
        chat_logs = ChatLogs.objects.filter(user=user).order_by("created_at")
        return [
            MessageDTO(
                user=log.user,
                role=RoleType(log.role),
                content=log.content,
                invisible=log.invisible,
                file_path=log.file.url if log.file else None,
                file_name=log.file.name if log.file else None,
            )
            for log in chat_logs
        ]

    @staticmethod
    def find_visible_chat_history(user: User) -> list[MessageDTO]:
        chat_logs = ChatLogs.objects.filter(user=user, invisible=False).order_by(
            "created_at"
        )
        return [
            MessageDTO(
                user=log.user,
                role=RoleType(log.role),
                content=log.content,
                invisible=log.invisible,
                file_path=log.file.url if log.file else None,
                file_name=log.file.name if log.file else None,
            )
            for log in chat_logs
        ]

    @staticmethod
    def insert(message: MessageDTO):
        message.to_entity().save()

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])
