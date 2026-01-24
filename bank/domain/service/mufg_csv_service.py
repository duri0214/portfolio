import csv
import io
from datetime import datetime
from typing import Optional
from bank.domain.valueobject.mufg_csv_row import MufgCsvRow


class MufgCsvService:
    OLD_HEADERS = ["日付", "摘要", "摘要内容", "支払い金額", "預かり金額", "差引残高"]
    NEW_HEADERS = [
        "日付",
        "摘要",
        "摘要内容",
        "支払い金額",
        "預かり金額",
        "差引残高",
        "メモ",
        "未資金化区分",
        "入払区分",
    ]

    def process_csv_content(self, content: str, filename: str = "") -> list[MufgCsvRow]:
        # BOM削除
        content = content.lstrip("\ufeff")
        lines = content.splitlines()
        header_index = self._find_header_index(lines, filename)

        header_line = lines[header_index].strip()

        # カンマまたはタブで分割を試みる
        if "\t" in header_line:
            actual_headers = [h.strip().strip('"') for h in header_line.split("\t")]
            delimiter = "\t"
        else:
            actual_headers = [h.strip().strip('"') for h in header_line.split(",")]
            delimiter = ","

        # 空の要素を除去（末尾のカンマなどで発生する）
        actual_headers = [h for h in actual_headers if h]

        is_old_format = self._validate_headers(actual_headers, filename)

        csv_data = "\n".join(lines[header_index:])
        reader = csv.DictReader(
            io.StringIO(csv_data), delimiter=delimiter, skipinitialspace=True
        )

        parsed_rows = []
        for row_num, row in enumerate(reader, start=header_index + 2):
            # DictReaderのキーと値から引用符と空白を除去する
            cleaned_row = {
                k.strip().strip('"'): v.strip().strip('"') if v else v
                for k, v in row.items()
                if k
            }
            parsed_rows.append(
                self._parse_row(cleaned_row, row_num, is_old_format, filename)
            )

        return parsed_rows

    @staticmethod
    def _find_header_index(lines: list[str], filename: str) -> int:
        for i, line in enumerate(lines):
            if "日付" in line and "摘要" in line:
                return i

        # ヘッダーが見つからなかった場合、比較のために最初の1行を取得してエラーに含める
        first_line = lines[0] if lines else "空のファイル"
        raise ValueError(
            f"ファイル `{filename}`: CSVファイルに有効なヘッダーが見つかりませんでした。\n\n"
            f"**期待される項目（例）**:\n`{', '.join(MufgCsvService.NEW_HEADERS[:6])}...` \n\n"
            f"**実際の1行目**:\n`{first_line}`"
        )

    def _validate_headers(self, actual_headers: list[str], filename: str) -> bool:
        # 必要な列がすべて含まれているかを確認する（順序や余計な空列に依存しないようにする）
        def contains_all(expected, actual):
            return all(item in actual for item in expected) and len(actual) >= len(
                expected
            )

        is_old = contains_all(self.OLD_HEADERS, actual_headers) and len(
            actual_headers
        ) == len(self.OLD_HEADERS)
        is_new = contains_all(self.NEW_HEADERS, actual_headers) and len(
            actual_headers
        ) == len(self.NEW_HEADERS)

        if is_old:
            return True
        elif is_new:
            return False
        else:
            # 形式が一致しない場合、期待されるヘッダーを表示する
            expected_new = ", ".join(self.NEW_HEADERS)
            expected_old = ", ".join(self.OLD_HEADERS)
            actual_headers_str = ", ".join(actual_headers)

            raise ValueError(
                f"ファイル `{filename}`: 未知のヘッダー形式です。\n\n"
                f"**期待されるヘッダー**:\n"
                f"- 新形式: `{expected_new}`\n"
                f"- 旧形式: `{expected_old}`\n\n"
                f"**実際のヘッダー**:\n"
                f"`{actual_headers_str}`"
            )

    def _parse_row(
        self, row: dict, row_num: int, is_old_format: bool, filename: str
    ) -> MufgCsvRow:
        try:
            trade_date = datetime.strptime(row["日付"], "%Y/%m/%d").date()
        except (ValueError, KeyError):
            raise ValueError(
                f"ファイル '{filename}' (行 {row_num}): 日付の形式が正しくありません。"
            )

        # 整合性チェック
        year_month = trade_date.year * 100 + trade_date.month
        if is_old_format:
            if year_month > 201303:
                raise ValueError(
                    f"ファイル '{filename}' (行 {row_num}): 旧形式のヘッダーですが、2013年3月より後のデータ({trade_date})が含まれています。"
                )
        else:
            if year_month <= 201303:
                raise ValueError(
                    f"ファイル '{filename}' (行 {row_num}): 新形式のヘッダーですが、2013年3月以前のデータ({trade_date})が含まれています。"
                )

        return MufgCsvRow(
            trade_date=trade_date,
            summary=row["摘要"],
            summary_detail=row["摘要内容"],
            payment_amount=self._parse_amount(row.get("支払い金額")),
            deposit_amount=self._parse_amount(row.get("預かり金額")),
            balance=self._parse_amount(row.get("差引残高")),
            inout_type=row.get("入払区分"),
            memo=row.get("メモ"),
            uncollected_flag=row.get("未資金化区分"),
        )

    @staticmethod
    def _parse_amount(value: str) -> Optional[int]:
        if not value or value.strip() == "":
            return None
        return int(value.replace(",", ""))
