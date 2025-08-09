from django.db.models import QuerySet

from ai_agent.models import Entity, Message, ActionHistory, RagMaterial


class TurnManagementRepository:
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
    def get_rag_source_merged(material_type: str, separator="\n\n") -> str:
        """指定されたmaterial_typeに基づいてRagMaterialから全てのレコードを取得して結合したテキストを返す

        Args:
            material_type (str): 取得する素材のタイプ（DATA_SOURCE_CHOICESに準拠）
            separator (str, optional): 複数レコードを結合する際の区切り文字。デフォルトは改行2つ。

        Note:
            複数のRagMaterialレコードが存在する場合、全てのレコードを取得して
            指定されたセパレータで結合したテキストを返します。
            単一レコードの場合も同様に動作します。

        Returns:
            str: RagMaterialから取得した全レコードを結合したコンテンツ
        """
        materials = RagMaterial.objects.filter(material_type=material_type)
        if not materials.exists():
            return f"{material_type}に関する情報が見つかりませんでした。"

        # 1レコードの場合はそのまま返す
        if materials.count() == 1:
            return materials.first().source_text

        # 複数レコードの場合は結合して返す
        return separator.join([material.source_text for material in materials])

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
