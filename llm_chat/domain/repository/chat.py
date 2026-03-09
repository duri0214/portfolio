from django.contrib.auth.models import User

from llm_chat.domain.valueobject.chat import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    @staticmethod
    def _find_all_by_user(user: User) -> list[MessageDTO]:
        chat_logs = ChatLogs.objects.filter(user=user).order_by("created_at")
        return [log.to_message_dto() for log in chat_logs]

    @classmethod
    def find_chat_history(cls, user: User) -> list[MessageDTO]:
        return cls._find_all_by_user(user)

    @classmethod
    def find_visible_chat_history(cls, user: User) -> list[MessageDTO]:
        # 将来的に非表示フラグなどが導入されたらここでフィルタリングする
        return cls._find_all_by_user(user)

    @staticmethod
    def insert(message: MessageDTO):
        message.to_entity().save()

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])
