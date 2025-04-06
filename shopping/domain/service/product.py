import csv
import io

from shopping.models import Products


class CsvService:
    @staticmethod
    def process(csv_file):
        """CSVファイルから商品データを一括処理する"""
        decoded_file = csv_file.read().decode("utf-8-sig")
        io_string = io.StringIO(decoded_file)
        reader = csv.reader(io_string, delimiter=",", quotechar='"')

        # ヘッダー行をスキップ
        next(reader)

        results = {"success_count": 0, "error_count": 0, "errors": []}

        for record in reader:
            try:
                if len(record) < 4:
                    results["errors"].append(f"不十分なフィールド数: {record}")
                    results["error_count"] += 1
                    continue

                code = record[0].strip()
                name = record[1].strip()
                price = int(record[2].strip()) if record[2].strip() else 0
                description = record[3].strip() if len(record) > 3 else ""

                existing_product = Products.objects.filter(code=code).first()

                if existing_product:
                    existing_product.name = name
                    existing_product.price = price
                    existing_product.description = description
                    existing_product.save()
                else:
                    Products.objects.create(
                        code=code, name=name, price=price, description=description
                    )

                results["success_count"] += 1

            except Exception as e:
                error_message = f"レコード {record} の処理中にエラーが発生: {str(e)}"
                results["errors"].append(error_message)
                results["error_count"] += 1

        return results
