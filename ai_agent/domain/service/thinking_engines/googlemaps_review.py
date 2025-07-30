from ai_agent.domain.service.thinking_engines.base_rag_service import BaseRagService
from ai_agent.models import RagMaterial


class GoogleMapsReviewService(BaseRagService):
    """Google Mapsレビューに関するRAGサービス"""

    material_type = "googlemaps_review"
    relevant_keywords = [
        "店",
        "レストラン",
        "カフェ",
        "場所",
        "行った",
        "美味しい",
        "サービス",
    ]

    @classmethod
    def load_source_to_rag_material(cls):
        """Google Mapsレビューをデータソースから収集し、RagMaterialに保存します。

        Note:
            将来的にはGoogle Maps APIやスクレイピングツールを使用して
            レビューデータを取得し、ベクトル化してRagMaterialテーブルに保存します。
            現在は開発・テスト目的のみに使用されています。
        """
        # TODO: 実際のデータ収集とエンベディング処理を実装
        #  1. Google Maps APIやスクレイピングでレビューを収集
        #  2. レビューをテーマ別やカテゴリ別に整理
        #  3. 各レビューをベクトル化
        #  4. RagMaterialテーブルに保存（ベクトルとメタデータを含む）
        # 現在はシーダーで登録されたデータを使用するため、実装は保留
        # 基底クラスのメソッドを呼び出す
        super().load_source_to_rag_material()

    @classmethod
    def get_reviews(cls) -> str:
        """
        全てのGoogle Mapsレビューを取得して結合したテキストを返します。

        Note:
            現在はシーダーで登録した疑似レビューデータを使用しており、実際のGoogle Mapsからの
            データ収集は行われていません。開発・テスト目的の限定的なデータのみが利用可能です。
            基底クラスのget_content()メソッドは使用せず、複数レコードの取得と結合を
            独自に実装しています。

        Returns:
            str: 全てのGoogle Mapsレビュー素材を結合したテキスト
        """
        # レビューの場合は複数レコードを直接取得
        materials = RagMaterial.objects.filter(material_type=cls.material_type)
        if not materials.exists():
            return f"{cls.material_type}に関する情報が見つかりませんでした。"

        # 1レコードの場合はそのまま返す
        if materials.count() == 1:
            return materials.first().source_text

        # 複数レコードの場合は結合して返す
        return "\n\n".join([material.source_text for material in materials])

    @classmethod
    def generate_rag_response(cls, entity, input_text: str):
        """Google Mapsレビューに関する入力に対してRAGベースのレスポンスを生成する

        Args:
            entity (Entity): 応答を生成するエンティティ
            input_text (str): ユーザーからの入力テキスト

        Returns:
            Optional[str]: 生成された応答、または応答できない場合はNone
        """
        if not cls.can_respond(input_text, entity):
            return None

        # レビューの場合は特殊処理：複数のレビューを取得
        reviews = cls.get_reviews()

        # レスポンスを整形
        response = f"{entity.name}は以下のレビュー情報を提供します:\n\n"
        response += reviews

        # キーワードに応じた追加コメント
        if "レストラン" in input_text or "食事" in input_text:
            response += "\n\nこれらのレビューから、おすすめのレストランを選ぶ際の参考にしてください。"
        elif "カフェ" in input_text:
            response += "\n\nカフェでの作業環境についてのレビューも参考になるでしょう。"

        return response
