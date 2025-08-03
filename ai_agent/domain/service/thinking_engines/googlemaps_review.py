from ai_agent.domain.service.thinking_engines.base_rag_service import BaseRagService


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
            基底クラスのget_contents_mergedメソッドを使用して、複数レコードの取得と結合を行います。

        Returns:
            str: 全てのGoogle Mapsレビュー素材を結合したテキスト
        """
        return cls.get_contents_merged()
