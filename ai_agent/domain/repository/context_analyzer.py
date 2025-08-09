from ai_agent.models import RagMaterial


class ContextAnalyzerRepository:
    """
    コンテキスト分析に必要なデータを取得するリポジトリクラス

    このクラスは、エンティティの思考タイプに基づく適切なRAG素材の取得を主な責務とします。
    特定の思考タイプ（material_type）に関連するすべての素材を取得し、
    後続の処理で利用できる形式に加工します。

    注意:
        RAG実装は現在、単純に素材を結合しているだけですが、将来的には
        ベクトル検索（埋め込みベクトルを使用した類似度検索）による
        完全なRAG実装に置き換えられる予定です。

    このリポジトリは、主にContextAnalyzerServiceクラスから使用され、
    エンティティの専門分野に基づいたコンテキスト分析をサポートします。
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

            メタデータ情報を常に含めます。メタデータは素材のテキストの前に追加されます。

            この実装は簡易的なRAG (Retrieval Augmented Generation) であり、
            将来的にはベクトル検索を用いた本格的なRAG実装に置き換える予定です。

        Returns:
            str: RagMaterialから取得した全レコードを結合したコンテンツ
                このメソッドはメッセージの検索・取得のみを行い、メッセージの管理は行いません。
        """
        materials = RagMaterial.objects.filter(material_type=material_type)
        if not materials.exists():
            return f"{material_type}に関する情報が見つかりませんでした。"

        result_texts = []

        for material in materials:
            source_text = material.source_text

            processed_text = source_text
            if material.metadata:
                metadata_str = str(material.metadata)
                if metadata_str and metadata_str != "{}":
                    processed_text = f"メタデータ: {metadata_str}\n{source_text}"

            result_texts.append(processed_text)

        # 1レコードの場合はそのまま返す
        if materials.count() == 1:
            return result_texts[0]

        # 複数レコードの場合は結合して返す
        return separator.join(result_texts)
