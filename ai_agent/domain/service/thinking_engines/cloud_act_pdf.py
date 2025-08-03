from ai_agent.domain.service.thinking_engines.base_rag_service import BaseRagService
from lib.llm.valueobject.rag import PdfDataloader


class CloudActPdfService(BaseRagService):
    """Cloud Act PDFに関するRAGサービス"""

    _pdf_loader = None
    _pdf_path = "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf"
    material_type = "cloud_act_pdf"
    relevant_keywords = ["法律", "law", "cloud", "act", "クラウド", "法案"]

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
    def load_source_to_rag_material(cls):
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
        # 基底クラスのメソッドを呼び出す
        super().load_source_to_rag_material()

    @classmethod
    def get_pdf_content(cls):
        """Cloud Act PDFの内容を取得します。

        Note:
            現在はPDFファイルから直接抽出したテキストではなく、シーダーで事前に
            登録されたサンプルデータや要約が使用しています。

        Returns:
            str: PDFから抽出したテキスト（または事前登録されたサンプルデータ）
        """
        return cls.get_contents_merged()
