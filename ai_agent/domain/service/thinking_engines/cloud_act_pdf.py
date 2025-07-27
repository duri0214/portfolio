from ai_agent.models import RagMaterial
from lib.llm.valueobject.rag import PdfDataloader


class CloudActPdfService:
    _pdf_loader = None
    _pdf_path = "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf"

    @classmethod
    def _get_pdf_loader(cls):
        """シングルトンパターンでPDFローダーを取得

        Note:
            現在実際のPDF解析は行われておらず、あらかじめデータベースシーダーで
            登録したPDFの要約・抜粋を使用しています。このメソッドは将来的に
            実際のPDF解析を実装する際に使用される予定です。
        """
        if cls._pdf_loader is None:
            cls._pdf_loader = PdfDataloader(cls._pdf_path)
        return cls._pdf_loader

    @classmethod
    def load_pdf_to_rag_material(cls):
        """PDFを読み込んでRagMaterialに保存する

        Note:
            将来的にはPDFファイルを読み込み、テキスト抽出・セグメント分割・ベクトル化を行い、
            RagMaterialテーブルに保存します。現在は開発・テスト目的のみに使用されています。
        """
        # TODO: 実際のPDF読み込みとエンベディング処理を実装
        #  1. PDFファイルからテキストを抽出
        #  2. テキストをセグメントに分割
        #  3. 各セグメントをベクトル化
        #  4. RagMaterialテーブルに保存（ベクトルとメタデータを含む）
        loader = cls._get_pdf_loader()
        # 現在はシーダーで登録されたデータを使用するため、実装は保留

    @staticmethod
    def can_respond(input_text: str, entity) -> bool:
        """
        Cloud Act PDFに基づいてエンティティが応答可能かどうかを判定します。

        Args:
            input_text (str): チェック対象の入力テキスト
            entity (Entity): 評価対象のエンティティ

        Returns:
            bool: 入力テキストが「法律」または「cloud act」に関連する場合はTrue
        """
        # PDFデータの内容に基づいて、このエンティティが応答すべきかを判断
        # 現時点では、特定のキーワードに基づく簡易な判定
        relevant_keywords = ["法律", "law", "cloud", "act", "クラウド", "法案"]
        return any(
            keyword.lower() in input_text.lower() for keyword in relevant_keywords
        )
