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
        actual_headers = [h.strip() for h in header_line.split(",")]

        is_old_format = self._validate_headers(actual_headers, filename)

        csv_data = "\n".join(lines[header_index:])
        reader = csv.DictReader(io.StringIO(csv_data))

        parsed_rows = []
        for row_num, row in enumerate(reader, start=header_index + 2):
            parsed_rows.append(self._parse_row(row, row_num, is_old_format, filename))

        return parsed_rows

    @staticmethod
    def _find_header_index(lines: list[str], filename: str) -> int:
        for i, line in enumerate(lines):
            if "日付" in line and "摘要" in line:
                return i
        raise ValueError(
            f"ファイル '{filename}': CSVファイルに有効なヘッダーが見つかりませんでした。"
        )

    def _validate_headers(self, actual_headers: list[str], filename: str) -> bool:
        if actual_headers == self.OLD_HEADERS:
            return True
        elif actual_headers == self.NEW_HEADERS:
            return False
        else:
            raise ValueError(f"ファイル '{filename}': 未知のヘッダー形式です。")

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
