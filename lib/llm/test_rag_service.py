from pathlib import Path
from unittest import TestCase

from config.settings import BASE_DIR
from lib.llm.valueobject.rag import PdfDataloader


class TestPdfDataloader(TestCase):
    def test_this_pdf_has_pages_en(self):
        file_path = (
            Path(BASE_DIR)
            / "lib/llm/pdf_sample/doj_cloud_act_white_paper_2019_04_10.pdf"
        )

        dataloader = PdfDataloader(str(file_path))
        self.assertEqual(18, len(dataloader.pages))
        print(dataloader.data)

    def test_this_pdf_has_pages_jp(self):
        file_path = (
            Path(BASE_DIR)
            / "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
        )
        dataloader = PdfDataloader(str(file_path))
        self.assertEqual(6, len(dataloader.pages))
        print(dataloader.data)
