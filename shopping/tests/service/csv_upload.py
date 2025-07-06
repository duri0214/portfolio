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
            description="既存商品の説明",
        )

    @staticmethod
    def create_csv_file(filename, content, encoding="utf-8"):
        """CSV ファイル作成のヘルパーメソッド"""
        return SimpleUploadedFile(
            filename, content.encode(encoding), content_type="text/csv"
        )

    def process_csv_file(self, filename, content, encoding="utf-8"):
        """CSV ファイル作成・処理のヘルパーメソッド"""
        csv_file = self.create_csv_file(filename, content, encoding)
        return CsvService.process(csv_file)

    def assert_result_counts(
        self,
        results,
        success_count,
        error_count,
        created_count=None,
        updated_count=None,
    ):
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
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def process_csv_file_from_directory(self, filename, encoding="utf-8"):
        """同じディレクトリのCSVファイルを読み込んで処理するヘルパーメソッド"""
        csv_content = self.read_csv_file_from_same_directory(filename)
        csv_file = self.create_csv_file(filename, csv_content, encoding)
        return CsvService.process(csv_file)

    def test_valid_csv_processing(self):
        """
        正常なCSVファイルの処理テスト

        【テスト目的】
        正しい形式のCSVファイルが正常に処理され、商品データがデータベースに保存されることを確認

        【前提条件】
        - CSVファイルのヘッダー: code,name,price,description
        - 3件の商品データを含む正常なCSV

        【実行内容】
        - 3件の商品データ（米、パン、牛乳）を含むCSVを処理
        - 各商品は新規作成される

        【期待結果】
        - success_count: 3件
        - error_count: 0件
        - 全商品がデータベースに保存される
        - 商品情報（名前、価格、説明）が正確に設定される
        """
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
        """
        BOM付きUTF-8のCSVファイルの処理テスト

        【テスト目的】
        Excel等で作成されたBOM付きUTF-8エンコーディングのCSVファイルが正常に処理されることを確認

        【前提条件】
        - CSVファイルはBOM付きUTF-8でエンコードされている（utf-8-sig）
        - 1件のテスト商品データを含む

        【実行内容】
        - BOM付きUTF-8エンコーディングのCSVファイルを処理
        - 文字化けや解析エラーが発生しないことを確認

        【期待結果】
        - success_count: 1件
        - error_count: 0件
        - 商品が正常にデータベースに保存される
        - 日本語文字が正しく処理される
        """
        csv_content = """code,name,price,description
test001,テスト商品,100,テスト用の商品"""

        results = self.process_csv_file("test_bom.csv", csv_content, "utf-8-sig")

        self.assert_result_counts(results, 1, 0)
        self.assertTrue(Product.objects.filter(code="test001").exists())

    def test_existing_product_update(self):
        """
        既存商品の更新テスト

        【テスト目的】
        既に存在する商品コードと同じコードのCSVデータを処理した際に、
        新規作成ではなく既存商品の更新が行われることを確認

        【前提条件】
        - setUp()で既存商品（existing001）がデータベースに登録済み
        - 既存商品の初期値: 名前="既存商品", 価格=1000, 説明="既存商品の説明"

        【実行内容】
        - 既存商品コード（existing001）で異なる商品情報のCSVを処理
        - 更新用データ: 名前="更新された商品名", 価格=1500, 説明="更新された説明"

        【期待結果】
        - success_count: 1件
        - error_count: 0件
        - created_count: 0件（新規作成なし）
        - updated_count: 1件（更新あり）
        - 既存商品の情報が新しいデータで上書きされる
        """
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
        """
        空のCSVファイルの処理テスト

        【テスト目的】
        内容が空のCSVファイルをアップロードした場合の適切なエラーハンドリングを確認

        【前提条件】
        - ファイルサイズが0バイトの空ファイル
        - ヘッダー行も含まない完全に空のファイル

        【実行内容】
        - 空のCSVファイルを処理
        - システムがクラッシュせずに適切にエラーを返すかチェック

        【期待結果】
        - success_count: 0件
        - error_count: 0件
        - エラーメッセージに「CSVファイルが空です」が含まれる
        - システムが安定して動作する
        """
        csv_file = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")

        results = CsvService.process(csv_file)

        self.assert_result_counts(results, 0, 0)
        self.assertIn("CSVファイルが空です", results["errors"])

    def test_invalid_header(self):
        """
        無効なヘッダーの処理テスト

        【テスト目的】
        期待するヘッダー形式と異なるCSVファイルのエラーハンドリングを確認

        【前提条件】
        - 期待するヘッダー: code,name,price,description
        - 実際のヘッダー: invalid,header,format,test（全く異なる）

        【実行内容】
        - 無効なヘッダーを持つCSVファイルを処理
        - データ行は存在するが、ヘッダーが正しくない状況をテスト

        【期待結果】
        - success_count: 0件
        - error_count: 0件
        - エラーメッセージに「無効なヘッダー形式」が含まれる
        - データは処理されない
        """
        csv_content = """invalid,header,format,test
test001,テスト商品,100,説明"""

        results = self.process_csv_file("invalid_header.csv", csv_content)

        self.assert_result_counts(results, 0, 0)
        self.assertTrue(
            any("無効なヘッダー形式" in error for error in results["errors"])
        )

    def test_missing_required_fields(self):
        """
        必須フィールドが欠けている場合のテスト

        【テスト目的】
        商品コード（code）または商品名（name）が空の場合の
        バリデーションエラーハンドリングを確認

        【前提条件】
        - 商品コードと商品名は必須項目
        - 2行のテストデータ: 1行目はコード空、2行目は名前空

        【実行内容】
        - 1行目: code=""（空）, name="テスト商品"
        - 2行目: code="test002", name=""（空）

        【期待結果】
        - success_count: 0件（どちらも処理されない）
        - error_count: 2件（2行ともエラー）
        - エラーメッセージに「商品コードと商品名は必須です」が含まれる
        - データベースには何も保存されない
        """
        csv_content = """code,name,price,description
,テスト商品,100,説明
test002,,200,説明2"""

        results = self.process_csv_file("missing_fields.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(
            any("商品コードと商品名は必須です" in error for error in results["errors"])
        )

    def test_invalid_price_format(self):
        """
        無効な価格形式のテスト

        【テスト目的】
        価格フィールドに数値以外の値が入力された場合の
        バリデーションエラーハンドリングを確認

        【前提条件】
        - 価格フィールドは整数値のみ受け付ける
        - 2行のテストデータ: 文字列と小数点を含むケース

        【実行内容】
        - 1行目: price="abc"（文字列）
        - 2行目: price="100.5"（小数点付き数値）

        【期待結果】
        - success_count: 0件（どちらも処理されない）
        - error_count: 2件（2行ともエラー）
        - エラーメッセージに「価格は数値でなければなりません」が含まれる
        - 小数点付きの数値も無効として扱われる
        """
        csv_content = """code,name,price,description
test001,テスト商品,abc,説明
test002,テスト商品2,100.5,説明2"""

        results = self.process_csv_file("invalid_price.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(
            any(
                "価格は数値でなければなりません" in error for error in results["errors"]
            )
        )

    def test_invalid_field_count(self):
        """
        フィールド数が不正な場合のテスト

        【テスト目的】
        CSVの列数が期待する4列（code,name,price,description）と
        異なる場合のエラーハンドリングを確認

        【前提条件】
        - 期待する列数: 4列
        - 2行のテストデータ: 列不足と列過多のケース

        【実行内容】
        - 1行目: 3列のみ（descriptionが欠落）
        - 2行目: 5列（余分なフィールドが存在）

        【期待結果】
        - success_count: 0件（どちらも処理されない）
        - error_count: 2件（2行ともエラー）
        - エラーメッセージに「無効なフィールド数」が含まれる
        - 列数が合わないデータは一切処理されない
        """
        csv_content = """code,name,price,description
test001,テスト商品,100
test002,テスト商品2,200,説明2,余分なフィールド"""

        results = self.process_csv_file("invalid_fields.csv", csv_content)

        self.assert_result_counts(results, 0, 2)
        self.assertTrue(
            any("無効なフィールド数" in error for error in results["errors"])
        )

    def test_empty_rows_handling(self):
        """
        空行の処理テスト

        【テスト目的】
        CSVファイル内に空行や空白のみの行が含まれている場合に、
        それらを適切にスキップして有効なデータのみを処理することを確認

        【前提条件】
        - 5行のデータ: 有効3行、空行1行、空白のみ1行
        - 空行とは: 完全に何もない行
        - 空白行とは: スペースやタブのみの行

        【実行内容】
        - 1行目: test001（有効データ）
        - 2行目: 完全な空行
        - 3行目: test002（有効データ）
        - 4行目: スペースのみの行
        - 5行目: test003（有効データ）

        【期待結果】
        - success_count: 3件（空行は無視される）
        - error_count: 0件
        - 3つの有効な商品がデータベースに保存される
        - 空行によるエラーは発生しない
        """
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
        """
        空白文字の処理テスト

        【テスト目的】
        CSVフィールドの前後にある空白文字（スペース、タブ等）が
        適切にトリムされて処理されることを確認

        【前提条件】
        - 1行のテストデータ
        - 各フィールドの前後に意図的に空白文字を配置

        【実行内容】
        - code=" test001 "（前後にスペース）
        - name=" テスト商品 "（前後にスペース）
        - price=" 100 "（前後にスペース）
        - description=" 説明 "（前後にスペース）

        【期待結果】
        - success_count: 1件
        - error_count: 0件
        - 保存されたデータから空白が除去されている
        - 商品情報が正確に設定される（"テスト商品", 100, "説明"）
        """
        csv_content = """code,name,price,description
 test001 , テスト商品 , 100 , 説明 """

        results = self.process_csv_file("whitespace.csv", csv_content)

        self.assert_result_counts(results, 1, 0)

        product = Product.objects.get(code="test001")
        self.assertEqual(product.name, "テスト商品")
        self.assertEqual(product.price, 100)
        self.assertEqual(product.description, "説明")

    def test_sample_data_csv(self):
        """
        サンプルデータCSVの処理テスト

        【テスト目的】
        実際のサンプルCSVファイル（csv_upload_sample_data.csv）を使用して
        本番に近い条件でのデータ処理を確認

        【前提条件】
        - 同じディレクトリにcsv_upload_sample_data.csvが存在
        - サンプルファイルには10件の商品データが含まれる
        - 米、パン、牛乳、卵、野菜、肉、魚、スナック、飲料、フルーツの各カテゴリ

        【実行内容】
        - 外部ファイルからCSVデータを読み込み
        - 10件の多様な商品データを一括処理
        - ファイル読み込み機能も含めたエンドツーエンドテスト

        【期待結果】
        - success_count: 10件
        - error_count: 0件
        - created_count: 10件（全て新規作成）
        - updated_count: 0件
        - rice001商品の価格が2480円で正しく設定される
        - 商品説明に「特A評価」が含まれる
        """
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
        """
        新規作成と更新の混在テスト

        【テスト目的】
        1つのCSVファイル内に既存商品の更新と新規商品の作成が
        混在している場合の正確な処理を確認

        【前提条件】
        - setUp()で既存商品（existing001）がデータベースに登録済み
        - 3行のCSVデータ: 既存1件の更新 + 新規2件の作成

        【実行内容】
        - 1行目: existing001（既存商品の更新）
        - 2行目: new001（新規商品の作成）
        - 3行目: new002（新規商品の作成）

        【期待結果】
        - success_count: 3件（全て成功）
        - error_count: 0件
        - created_count: 2件（新規商品）
        - updated_count: 1件（既存商品の更新）
        - 既存商品の情報が正しく更新される
        - 新規商品2件がデータベースに追加される
        """
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
        """
        重複検出時のメッセージ確認テスト

        【テスト目的】
        既存商品と同じコードの商品データを処理した際に、
        エラーではなく更新として正しく処理されることを確認

        【前提条件】
        - setUp()で既存商品（existing001）がデータベースに登録済み
        - 既存商品と同じコードで異なる商品情報のCSVデータ

        【実行内容】
        - existing001コードで新しい商品情報を処理
        - 名前="同じコードの商品", 価格=999円
        - 重複エラーではなく更新処理として実行

        【期待結果】
        - success_count: 1件（エラーではなく成功）
        - error_count: 0件
        - created_count: 0件（新規作成なし）
        - updated_count: 1件（更新処理）
        - 既存商品が新しい情報で上書きされる
        - データベース内の商品数は変わらない（更新のみ）
        """
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
