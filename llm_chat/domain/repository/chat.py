from llm_chat.domain.valueobject.chat import MyChatCompletionMessage
from llm_chat.models import ChatLogsWithLine


class ChatLogRepository:
    def __init__(self):
        pass

    @staticmethod
    def find_chatlog_by_id(pk: int) -> list[ChatLogsWithLine]:
        return ChatLogsWithLine.objects.get(pk=pk)

    @staticmethod
    def find_chatlog_by_user_id(user_id: int) -> list[ChatLogsWithLine]:
        return ChatLogsWithLine.objects.filter(user_id=user_id)

    @staticmethod
    def insert(my_chat_completion_message: MyChatCompletionMessage):
        ChatLogsWithLine.objects.create(
            user=my_chat_completion_message.user,
            role=my_chat_completion_message.role,
            content=my_chat_completion_message.content,
            file_path=my_chat_completion_message.file_path,
            invisible=my_chat_completion_message.invisible,
        )

    @staticmethod
    def bulk_insert(my_chat_completion_message_list: list[MyChatCompletionMessage]):
        ChatLogsWithLine.objects.bulk_create(
            [x.to_entity() for x in my_chat_completion_message_list]
        )

    @staticmethod
    def upsert(my_chat_completion_message: MyChatCompletionMessage):
        ChatLogsWithLine.objects.update_or_create(
            id=my_chat_completion_message.id,
            defaults={
                "user": my_chat_completion_message.user,
                "role": my_chat_completion_message.role,
                "content": my_chat_completion_message.content,
                "file_path": my_chat_completion_message.file_path,
                "invisible": my_chat_completion_message.invisible,
            },
        )
