from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import ChatLogs


class ChatLogRepository:
    """
    チャット履歴の永続化を担当するリポジトリ。

    データベース（ChatLogsモデル）との間でのメッセージDTOの保存、
    履歴の取得、および全削除などの操作をカプセル化します。
    """

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
        chat_log = message.to_entity()
        chat_log.save()
        return chat_log

    @staticmethod
    def bulk_insert(message_list: list[MessageDTO]):
        ChatLogs.objects.bulk_create([x.to_entity() for x in message_list])

    @staticmethod
    def count_answered_questions(user: User) -> int:
        """
        ユーザーが回答済みの問題数をカウントします。

        チャット履歴からユーザーのメッセージ数を取得し、
        開始メッセージ（「なぞなぞを始めてください」）を除いた数を返します。

        Args:
            user (User): 対象ユーザー。

        Returns:
            int: 回答済みの問題数。
        """
        user_message_count = ChatLogs.objects.filter(
            user=user, role=RoleType.USER
        ).count()
        return user_message_count - 1  # 開始メッセージを除く

    @staticmethod
    def update_riddle_scores(message_id: int, scores: dict, append_text: str) -> None:
        """
        指定されたメッセージに単問評価スコアを保存し、内容に評価行を追記します。
        """
        if not message_id:
            return

        try:
            chat_log = ChatLogs.objects.get(pk=message_id)
        except ChatLogs.DoesNotExist:
            return

        if append_text and append_text in (chat_log.content or ""):
            chat_log.riddle_scores = scores
            chat_log.save(update_fields=["riddle_scores"])
            return

        chat_log.riddle_scores = scores
        if append_text:
            separator = "\n\n" if chat_log.content else ""
            chat_log.content = f"{chat_log.content}{separator}{append_text}"
            chat_log.save(update_fields=["riddle_scores", "content"])
        else:
            chat_log.save(update_fields=["riddle_scores"])

    @staticmethod
    def fetch_riddle_scores(user: User) -> list[dict]:
        """
        ユーザーのなぞなぞ単問評価スコアを時系列で取得します。
        """
        logs = (
            ChatLogs.objects.filter(
                user=user,
                role=RoleType.USER,
                use_case_type=UseCaseType.RIDDLE,
                riddle_scores__isnull=False,
            )
            .order_by("created_at")
            .values_list("riddle_scores", flat=True)
        )
        return list(logs)
