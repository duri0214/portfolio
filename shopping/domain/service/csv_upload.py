import csv
import io
import logging

from shopping.models import Product

logger = logging.getLogger(__name__)


class CsvService:
    @staticmethod
    def process(csv_file):
        """
        CSVファイルから商品データを一括処理し、Product モデルに登録・更新する

        期待されるCSV形式:
            - ヘッダー行: code,name,price,description
            - データ行: 各列がカンマ区切りで、上記の順序で値が含まれる

        バリデーション:
            - ヘッダー行が正確に一致していること
            - 各行は正確に4フィールドを含むこと
            - 商品コード(code)と商品名(name)は必須
            - 価格(price)は数値に変換可能であること

        処理内容:
            - 既存の商品コードの場合は商品情報を更新
            - 新規の商品コードの場合は新しいレコードを作成

        Args:
            csv_file: アップロードされたCSVファイルオブジェクト

        Returns:
            dict: 処理結果を含む辞書
                - success_count: 正常に処理された行数
                - error_count: エラーが発生した行数
                - errors: エラーメッセージのリスト（行番号付き）

        エラー例:
            - CSVファイルが空の場合
            - ヘッダー形式が不正な場合
            - フィールド数が不正な場合
            - 必須フィールドが欠けている場合
            - 価格が数値でない場合
        """
        logger.info(f"CSV処理開始: ファイル名={csv_file.name}, サイズ={csv_file.size}バイト")

        results = {
            "success_count": 0, 
            "error_count": 0, 
            "errors": [],
            "created_count": 0,
            "updated_count": 0
        }

        try:
            # ファイルポインタを先頭に戻す
            csv_file.seek(0)

            # 複数の文字コードを試行
            raw_data = csv_file.read()
            decoded_file = None

            for encoding in ['utf-8-sig', 'utf-8', 'shift_jis', 'cp932']:
                try:
                    decoded_file = raw_data.decode(encoding)
                    logger.info(f"文字コード検出成功: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if decoded_file is None:
                results["errors"].append("サポートされていない文字コードです")
                return results

            # 空のファイルをチェック
            if not decoded_file.strip():
                results["errors"].append("CSVファイルが空です")
                return results

            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=",", quotechar='"')

            # ヘッダー行の検証
            try:
                headers = next(reader)
                headers = [h.strip() for h in headers]  # 空白文字を除去
                expected_headers = ["code", "name", "price", "description"]

                logger.info(f"ヘッダー行: {headers}")

                if headers != expected_headers:
                    results["errors"].append(
                        f"無効なヘッダー形式: {headers}, 期待される形式: {expected_headers}"
                    )
                    return results
            except StopIteration:
                results["errors"].append("CSVファイルが空です")
                return results

            # データ行の処理
            for row_num, record in enumerate(reader, start=2):
                try:
                    # 空行をスキップ
                    if not record or all(not field.strip() for field in record):
                        logger.debug(f"行 {row_num}: 空行をスキップ")
                        continue

                    if len(record) != 4:
                        results["errors"].append(
                            f"行 {row_num}: 無効なフィールド数 ({len(record)}). 正確に4フィールドが必要です"
                        )
                        results["error_count"] += 1
                        continue

                    code = record[0].strip()
                    name = record[1].strip()
                    price_str = record[2].strip()
                    description = record[3].strip()

                    logger.debug(f"行 {row_num}: code={code}, name={name}, price={price_str}")

                    # 必須フィールドの検証
                    if not code or not name:
                        results["errors"].append(
                            f"行 {row_num}: 商品コードと商品名は必須です"
                        )
                        results["error_count"] += 1
                        continue

                    # 価格の変換と検証
                    try:
                        price = int(price_str) if price_str else 0
                    except ValueError:
                        results["errors"].append(
                            f"行 {row_num}: 価格は数値でなければなりません: '{price_str}'"
                        )
                        results["error_count"] += 1
                        continue

                    # 商品の登録・更新
                    existing_product = Product.objects.filter(code=code).first()

                    if existing_product:
                        existing_product.name = name
                        existing_product.price = price
                        existing_product.description = description
                        existing_product.save()
                        results["updated_count"] += 1
                        logger.debug(f"商品更新: {code} ({existing_product.name})")
                    else:
                        Product.objects.create(
                            code=code, name=name, price=price, description=description
                        )
                        results["created_count"] += 1
                        logger.debug(f"新規商品作成: {code} ({name})")

                    results["success_count"] += 1

                except Exception as e:
                    error_message = f"行 {row_num}: 処理中にエラーが発生: {str(e)}"
                    results["errors"].append(error_message)
                    results["error_count"] += 1
                    logger.error(error_message)

        except Exception as e:
            error_message = f"CSV処理中に予期しないエラーが発生: {str(e)}"
            results["errors"].append(error_message)
            results["error_count"] += 1
            logger.error(error_message)

        logger.info(f"CSV処理完了: 成功={results['success_count']} (新規={results['created_count']}, 更新={results['updated_count']}), エラー={results['error_count']}")
        return results
