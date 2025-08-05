from ai_agent.models import Message, RagMaterial


class ResponseGeneratorRepository:
    """エンティティの応答生成に必要なデータを取得するリポジトリクラス

    このクラスは、以下の主要な責務を持ちます：
    1. エンティティの思考タイプに基づく適切なRAG素材の取得
    2. チャット履歴の管理と最新メッセージの取得

    RAG素材については、特定の思考タイプ（material_type）に関連するすべての素材を取得し、
    後続の処理で利用できる形式に加工します。またチャット履歴については、最新の会話文脈を
    提供し、エンティティが一貫した対話を行えるようサポートします。

    注意:
        RAG実装は現在、単純に素材を結合しているだけですが、将来的には
        ベクトル検索（埋め込みベクトルを使用した類似度検索）による
        完全なRAG実装に置き換えられる予定です。
    """

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
