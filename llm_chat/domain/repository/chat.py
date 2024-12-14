from llm_chat.domain.valueobject.chat import MessageDTO
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
    def insert(message: MessageDTO):
        ChatLogsWithLine.objects.create(
            user=message.user,
            role=message.role.value,
            content=message.content,
            file_path=message.file_path,
            invisible=message.invisible,
        )

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogsWithLine.objects.bulk_create([x.to_entity() for x in message_list])

    @staticmethod
    def update_file_path(message: MessageDTO):
        """
        指定されたメッセージDTO（ユーザー、役割、コンテンツ）に基づいて
        該当のChatLogsWithLineレコードのfile_pathフィールドを更新します。
        このメソッドは、テキストから生成された画像（Dalle）や音声ファイル（Text2Speech）などの
        ファイルパスを更新するために利用されます。

        Args:
            message (MessageDTO): 更新するfile_path情報を含むメッセージDTO

        """
        ChatLogsWithLine.objects.filter(
            user=message.user, role=message.role, content=message.content
        ).update(
            file_path=message.file_path,
        )
