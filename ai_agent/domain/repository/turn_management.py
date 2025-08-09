from django.db.models import QuerySet

from ai_agent.models import Entity, Message, ActionHistory


class TurnManagementRepository:
    """
    ターン管理に関するデータアクセスを提供するリポジトリクラス

    このクラスは、エンティティのアクション順序管理、メッセージ作成、
    アクション履歴の取得などのデータアクセス機能を提供します。
    TurnManagementServiceから主に使用され、会話のターン進行をサポートします。
    """

    @staticmethod
    def get_entities_ordered() -> QuerySet:
        """
        next_turnフィールドの昇順で並べられたEntityを取得します。
        これにより、次に行動するエンティティの順序を決定できます。

        システム内のすべてのエンティティを含み、next_turnが未設定（null）の場合でも適切に動作します。

        Returns:
            QuerySet[Entity]: next_turnで昇順ソートされたEntityのクエリセット
        """
        return Entity.objects.order_by("next_turn")

    @staticmethod
    def create_message(content: str, action_history: ActionHistory) -> Message:
        """
        アクション履歴に関連するエンティティのメッセージを作成し、データベースに保存します。
        同時にアクション履歴を完了状態に更新します。

        Args:
            content (str): メッセージの内容
            action_history (ActionHistory): 完了状態に更新するアクション履歴

        Returns:
            Message: 作成されたメッセージオブジェクト
        """
        message = Message.objects.create(
            entity=action_history.entity, message_content=content
        )

        # アクション履歴を完了状態に更新
        action_history.done = True
        action_history.save()

        return message

    @staticmethod
    def get_recent_chat_messages(limit: int = 5) -> str:
        """直近のチャットメッセージを取得し、内容を連結して返します

        Args:
            limit (int): 取得するメッセージの数

        Returns:
            str: 連結されたチャットメッセージ内容
        """
        messages = Message.objects.order_by("-created_at")[:limit]
        return "\n".join([msg.message_content for msg in messages])

    @staticmethod
    def get_latest_chat_message() -> Message | None:
        """最新のチャットメッセージを1件だけ取得します

        Returns:
            Message | None: 最新のチャットメッセージ（存在しない場合はNone）
        """
        return Message.objects.order_by("-created_at").first()
