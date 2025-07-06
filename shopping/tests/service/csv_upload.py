import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from shopping.domain.service.csv_upload import CsvService
from shopping.models import Product


class CsvServiceTest(TestCase):
    def setUp(self):
        """テスト用のセットアップ"""
        # テスト用の既存商品を作成
        Product.objects.create(
            code="existing001",
            name="既存商品",
            price=1000,
            description="既存商品の説明"
        )

    @staticmethod
    def create_csv_file(filename, content, encoding='utf-8'):
        """CSV ファイル作成のヘルパーメソッド"""
        return SimpleUploadedFile(
            filename,
            content.encode(encoding),
            content_type="text/csv"
        )

    def process_csv_file(self, filename, content, encoding='utf-8'):
        """CSV ファイル作成・処理のヘルパーメソッド"""
        csv_file = self.create_csv_file(filename, content, encoding)
        return CsvService.process(csv_file)

    def assert_result_counts(self, results, success_count, error_count, created_count=None, updated_count=None):
        """結果の数値を検証するヘルパーメソッド"""
        self.assertEqual(results["success_count"], success_count)
        self.assertEqual(results["error_count"], error_count)
        if created_count is not None:
            self.assertEqual(results["created_count"], created_count)
        if updated_count is not None:
            self.assertEqual(results["updated_count"], updated_count)

    def assert_no_errors(self, results):
        """エラーがないことを検証するヘルパーメソッド"""
        self.assertEqual(len(results["errors"]), 0)

    @staticmethod
    def read_csv_file_from_same_directory(filename):
        """同じディレクトリからCSVファイルを読み込むヘルパーメソッド"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, filename)
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def process_csv_file_from_directory(self, filename, encoding='utf-8'):
        """同じディレクトリのCSVファイルを読み込んで処理するヘルパーメソッド"""
        csv_content = self.read_csv_file_from_same_directory(filename)
        csv_file = self.create_csv_file(filename, csv_content, encoding)
        return CsvService.process(csv_file)

    def test_valid_csv_processing(self):
        """正常なCSVファイルの処理テスト"""
        csv_content = """code,name,price,description
rice001,特選コシヒカリ（新潟県産）,2480,5kg入り 令和5年産 特A評価
bread001,生食パン（高級食パン）,580,1斤 北海道産小麦100%使用
milk001,北海道牛乳,238,1000ml 成分無調整"""

        results = self.process_csv_file("test.csv", csv_content)

        self.assert_result_counts(results, 3, 0)
        self.assert_no_errors(results)

        # データベースに正しく保存されているかチェック
        self.assertTrue(Product.objects.filter(code="rice001").exists())
        self.assertTrue(Product.objects.filter(code="bread001").exists())
        self.assertTrue(Product.objects.filter(code="milk001").exists())

        # 商品情報が正しく設定されているかチェック
        rice_product = Product.objects.get(code="rice001")
        self.assertEqual(rice_product.name, "特選コシヒカリ（新潟県産）")
        self.assertEqual(rice_product.price, 2480)
        self.assertEqual(rice_product.description, "5kg入り 令和5年産 特A評価")

    def test_csv_with_bom(self):
        """BOM付きUTF-8のCSVファイルの処理テスト"""
        csv_content = """code,name,price,description
test001,テスト商品,100,テスト用の商品"""

        results = self.process_csv_file("test_bom.csv", csv_content, 'utf-8-sig')

        self.assert_result_counts(results, 1, 0)
        self.assertTrue(Product.objects.filter(code="test001").exists())

    def test_existing_product_update(self):
        """既存商品の更新テスト"""
        csv_content = """code,name,price,description
existing001,更新された商品名,1500,更新された説明"""

        results = self.process_csv_file("update_test.csv", csv_content)

        self.assert_result_counts(results, 1, 0, 0, 1)

        # 既存商品が更新されているかチェック
        updated_product = Product.objects.get(code="existing001")
        self.assertEqual(updated_product.name, "更新された商品名")
        self.assertEqual(updated_product.price, 1500)
        self.assertEqual(updated_product.description, "更新された説明")

    def test_empty_csv_file(self):
        """空のCSVファイルの処理テスト"""
        csv_file = SimpleUploadedFile(
            "empty.csv",
            b"",
            content_type="text/csv"
        )

        results = CsvService.process(csv_file)

        self.assert_result_counts(results, 0, 0)
        self.assertIn("CSVファイルが空です", results["errors"])

    def test_invalid_header(self):
        """無効なヘッダーの処理テスト"""
        csv_content = """invalid,header,format,test
test001,テスト商品,100,説明"""

        results = self.process_csv_file("invalid_header.csv", csv_content)

        self.assert_result_counts(results, 0, 0)
        self.assertTrue(any("無効なヘッダー形式" in error for error in results["errors"]))

    def test_missing_required_fields(self):
        """必須フィールドが欠けている場合のテスト"""
        csv_content = """code,name,price,description
,テスト商品,100,説明
test002,,200,説明2"""

        results = self.process_csv_file("missing_fields.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(any("商品コードと商品名は必須です" in error for error in results["errors"]))

    def test_invalid_price_format(self):
        """無効な価格形式のテスト"""
        csv_content = """code,name,price,description
test001,テスト商品,abc,説明
test002,テスト商品2,100.5,説明2"""

        results = self.process_csv_file("invalid_price.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(any("価格は数値でなければなりません" in error for error in results["errors"]))

    def test_invalid_field_count(self):
        """フィールド数が不正な場合のテスト"""
        csv_content = """code,name,price,description
test001,テスト商品,100
test002,テスト商品2,200,説明2,余分なフィールド"""

        results = self.process_csv_file("invalid_fields.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(any("無効なフィールド数" in error for error in results["errors"]))

    def test_empty_rows_handling(self):
        """空行の処理テスト"""
        csv_content = """code,name,price,description
test001,テスト商品,100,説明

test002,テスト商品2,200,説明2
   ,   ,   ,   
test003,テスト商品3,300,説明3"""

        results = self.process_csv_file("empty_rows.csv", csv_content)

        self.assert_result_counts(results, 3, 0)
        self.assertTrue(Product.objects.filter(code="test001").exists())
        self.assertTrue(Product.objects.filter(code="test002").exists())
        self.assertTrue(Product.objects.filter(code="test003").exists())

    def test_whitespace_handling(self):
        """空白文字の処理テスト"""
        csv_content = """code,name,price,description
 test001 , テスト商品 , 100 , 説明 """

        results = self.process_csv_file("whitespace.csv", csv_content)

        self.assert_result_counts(results, 1, 0)

        product = Product.objects.get(code="test001")
        self.assertEqual(product.name, "テスト商品")
        self.assertEqual(product.price, 100)
        self.assertEqual(product.description, "説明")

    def test_sample_data_csv(self):
        """サンプルデータCSVの処理テスト"""
        # 同じディレクトリのサンプルCSVファイルを読み込んでテスト
        results = self.process_csv_file_from_directory("csv_upload_sample_data.csv")

        self.assert_result_counts(results, 10, 0, 10, 0)
        self.assert_no_errors(results)

        # いくつかの商品をチェック
        self.assertTrue(Product.objects.filter(code="rice001").exists())
        self.assertTrue(Product.objects.filter(code="fruit001").exists())

        rice_product = Product.objects.get(code="rice001")
        self.assertEqual(rice_product.price, 2480)
        self.assertIn("特A評価", rice_product.description)

    def test_mixed_create_and_update(self):
        """新規作成と更新の混在テスト"""
        csv_content = """code,name,price,description
existing001,更新された既存商品,1500,更新された説明
new001,新規商品1,1000,新規商品1の説明
new002,新規商品2,2000,新規商品2の説明"""

        results = self.process_csv_file("mixed_test.csv", csv_content)

        self.assert_result_counts(results, 3, 0, 2, 1)

        # 既存商品が更新されているかチェック
        updated_product = Product.objects.get(code="existing001")
        self.assertEqual(updated_product.name, "更新された既存商品")
        self.assertEqual(updated_product.price, 1500)

        # 新規商品が作成されているかチェック
        self.assertTrue(Product.objects.filter(code="new001").exists())
        self.assertTrue(Product.objects.filter(code="new002").exists())

    def test_duplicate_detection_message(self):
        """重複検出時のメッセージ確認テスト"""
        # 最初に既存商品と同じコードでCSVを処理
        csv_content = """code,name,price,description
existing001,同じコードの商品,999,同じコードでの登録"""

        results = self.process_csv_file("duplicate_test.csv", csv_content)

        # 処理は成功するが、更新扱いになる
        self.assert_result_counts(results, 1, 0, 0, 1)

        # 既存商品が更新されているかチェック
        updated_product = Product.objects.get(code="existing001")
        self.assertEqual(updated_product.name, "同じコードの商品")
        self.assertEqual(updated_product.price, 999)

    def tearDown(self):
        """テスト後のクリーンアップ"""
        Product.objects.all().delete()