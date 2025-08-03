from ai_agent.models import Message


class ThinkingEngineProcessorRepository:
    """思考エンジン関連のデータアクセスを担当するリポジトリクラス

    Messageモデルに対する操作をカプセル化し、データアクセスの一貫性を確保します。
    """

    @staticmethod
    def get_recent_messages(limit: int = 5) -> str:
        """直近のメッセージを取得し、内容を連結して返します

        Args:
            limit (int): 取得するメッセージの数

        Returns:
            str: 連結されたメッセージ内容
        """
        messages = Message.objects.order_by("-created_at")[:limit]
        return "\n".join([msg.message_content for msg in messages])

    @staticmethod
    def get_latest_message() -> Message | None:
        """最新のメッセージを1件だけ取得します

        Returns:
            Message | None: 最新のメッセージ（存在しない場合はNone）
        """
        return Message.objects.order_by("-created_at").first()
