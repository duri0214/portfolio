from ai_agent.models import RagMaterial


class ResponseGeneratorRepository:
    """RAG素材を取得するためのリポジトリクラス

    このリポジトリはRagMaterialモデルから素材を取得し、必要に応じて
    複数のレコードを結合するなどの処理を行います。
    """

    @staticmethod
    def get_contents_merged(material_type: str, separator="\n\n") -> str:
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
