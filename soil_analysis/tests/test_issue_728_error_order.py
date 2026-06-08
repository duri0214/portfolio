from django.test import TestCase

from soil_analysis.domain.repository.chemical_import_error import (
    ChemicalImportErrorRepository,
)


class ErrorOrderTest(TestCase):
    def test_error_display_order(self):
        # エラーリポジトリをクリア
        ChemicalImportErrorRepository.delete_all()

        # エラーを順番に作成 (row=4, 5, 6 の順)
        ChemicalImportErrorRepository.create(
            row_number=4,
            land_name="FIELD001",
            message="row=4: 分析番号 1001 は既に取り込まれています。",
        )
        ChemicalImportErrorRepository.create(
            row_number=5,
            land_name="FIELD001",
            message="row=5: 分析番号 1002 は既に取り込まれています。",
        )
        ChemicalImportErrorRepository.create(
            row_number=6,
            land_name="FIELD001",
            message="row=6: 分析番号 1003 は既に取り込まれています。",
        )

        # Viewから取得
        errors = ChemicalImportErrorRepository.get_all()

        # 現在は降順になっているはず (6, 5, 4)
        # 修正後は昇順 (4, 5, 6) になるべき
        messages = [e.message for e in errors]
        print(f"Current order: {messages}")

        # 修正後は昇順 (4, 5, 6)
        self.assertIn("row=4", messages[0])
        self.assertIn("row=5", messages[1])
        self.assertIn("row=6", messages[2])
