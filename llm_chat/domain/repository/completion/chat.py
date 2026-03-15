from django.contrib.auth.models import User

from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    @staticmethod
    def find_chat_history(user: User) -> list[MessageDTO]:
        chat_logs = ChatLogs.objects.filter(user=user).order_by("created_at")
        return [chat_log.to_message_dto() for chat_log in chat_logs]

    @staticmethod
    def count() -> int:
        """
        チャット履歴の総件数を取得します。

        Returns:
            int: チャット履歴の件数。
        """
        return ChatLogs.objects.count()

    @staticmethod
    def clear_all() -> int:
        """
        すべてのチャット履歴を削除します。

        Returns:
            int: 削除されたレコードの件数。
        """
        deleted_count, _ = ChatLogs.objects.all().delete()
        return deleted_count

    @staticmethod
    def insert(message: MessageDTO):
        message.to_entity().save()

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])
