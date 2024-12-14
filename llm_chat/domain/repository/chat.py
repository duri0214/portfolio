from django.contrib.auth.models import User
from django.db.models import Q, QuerySet

from llm_chat.domain.valueobject.chat import MessageDTO
from llm_chat.models import ChatLogs


class ChatLogRepository:
    def __init__(self):
        pass

    @staticmethod
    def find_chat_history(user: User) -> QuerySet:
        return ChatLogs.objects.filter(user=user)

    @staticmethod
    def find_last_audio_log(user: User):
        return ChatLogs.objects.filter(
            Q(user=user)
            & Q(role="user")
            & Q(file_path__endswith=".mp3")
            & Q(invisible=False)
        ).last()

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])

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
        ChatLogs.objects.filter(
            user=message.user, role=message.role, content=message.content
        ).update(
            file_path=message.file_path,
        )
