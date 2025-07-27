from lib.llm.valueobject.rag import PdfDataloader


class CloudActPdfService:
    _pdf_loader = None

    @classmethod
    def _get_pdf_loader(cls):
        """シングルトンパターンでPDFローダーを取得"""
        if cls._pdf_loader is None:
            cls._pdf_loader = PdfDataloader(
                "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf"
            )
        return cls._pdf_loader

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
