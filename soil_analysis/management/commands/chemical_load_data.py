"""川田研究所フォーマットのExcelファイルから化学分析データを取り込むDjangoコマンド

川田研究所が提供する化学分析結果Excel(.xlsx)を読み込み、
LandScoreChemicalテーブルにデータを一括登録する。

使用方法:
    python manage.py chemical_load_data <excel_path> --land-ledger-id=<ledger_id> [--overwrite]

例:
    python manage.py chemical_load_data data.xlsx --land-ledger-id=123
    python manage.py chemical_load_data data.xlsx --land-ledger-id=123 --overwrite
"""

from decimal import Decimal, InvalidOperation

import unicodedata
from django.core.management.base import BaseCommand
from django.db import transaction
from openpyxl import load_workbook

from soil_analysis.domain.valueobject.chemical_report.fields import (
    CHEMICAL_FIELD_ALIAS_TO_KEY,
    CHEMICAL_FIELD_KEYS,
    normalize_text,
)
from soil_analysis.models import LandBlock, LandLedger, LandScoreChemical

# 取り込み対象のブロック名（9ブロック固定）
BLOCK_NAMES = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3")

# 取り込みモードを示すremark文字列（圃場レベルのデータを9ブロックにコピーしたことを示す）
REMARK_IMPORT_MODE = "import_mode=field_level_copied_to_9_blocks"

# Excelで圃場名列として使われる可能性のある列名
LAND_NAME_ALIASES = ("圃場名", "圃場", "ほ場名", "ほ場")

# 正規化済み圃場名エイリアス（列名マッチング用）
NORMALIZED_LAND_NAME_ALIASES = {normalize_text(name) for name in LAND_NAME_ALIASES}


def parse_numeric_value(
    raw_value: object, row_number: int, column_name: str
) -> float | None:
    """Excelセルの値を数値（float）に変換する

    Excelシートから読み取った生の値を、化学分析データとして使用できる
    float型に変換する。空値やハイフン（欠測値）、パーセント記号付き数値などに対応。

    変換処理:
        1. None/空文字/ハイフン類 → None（欠測値）
        2. カンマ除去（例: "1,234" → "1234"）
        3. パーセント記号除去（例: "50%" → "50"）
        4. Decimal経由でfloatに変換（精度保持のため）

    Args:
        raw_value: Excelセルの生の値（文字列、数値、Noneなど）
        row_number: 行番号（エラーメッセージ用）
        column_name: 列名（エラーメッセージ用）

    Returns:
        変換後のfloat値、または欠測値の場合はNone

    Raises:
        ValueError: 数値変換に失敗した場合（行番号・列名・値を含むメッセージ）

    Examples:
        >>> parse_numeric_value("123", 1, "ec")
        123.0
        >>> parse_numeric_value("1,234.5", 1, "ec")
        1234.5
        >>> parse_numeric_value("50%", 1, "base_saturation")
        50.0
        >>> parse_numeric_value("-", 1, "ec")
        None
        >>> parse_numeric_value(None, 1, "ec")
        None
    """
    if raw_value is None:
        return None
    text = unicodedata.normalize("NFKC", str(raw_value)).strip()
    if text in ("", "-", "ー", "―"):
        return None
    text = text.replace(",", "")
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"数値変換失敗 row={row_number}, column={column_name}, value={raw_value}"
        ) from exc


def parse_kawada_worksheet(worksheet):
    """川田研究所フォーマットのExcelシートをパースして化学分析データを抽出する

    Excelシート全体をスキャンして以下の処理を行う:
        1. ヘッダ行を自動検出（圃場名列 + 分析項目列が揃った行）
        2. 列名を正規化してフィールドにマッピング
        3. 必須列の存在チェック（全17項目）
        4. データ行を1行ずつパースして数値変換

    川田研究所フォーマットの特徴:
        - ヘッダ行の位置が固定されていない（自動検出が必要）
        - 列名に全角・半角の表記ゆれがある
        - 圃場名列が必須（"圃場名", "圃場", "ほ場名", "ほ場"など）

    Args:
        worksheet: openpyxlのワークシートオブジェクト

    Returns:
        tuple[list[dict], list[str]]: (パース結果, エラーリスト)

        パース結果の各要素:
            {
                "row_number": int,        # Excel行番号（1始まり）
                "land_name": str,         # 圃場名
                "values": {               # フィールド名 -> 数値のマッピング
                    "ec": float | None,
                    "ph": float | None,
                    ...
                }
            }

        エラーリスト:
            - ヘッダ行が見つからない場合
            - 必須列が不足している場合
            - 数値変換エラーが発生した場合

    Examples:
        >>> from openpyxl import load_workbook
        >>> wb = load_workbook("kawada_data.xlsx", data_only=True)
        >>> parsed_rows, errors = parse_kawada_worksheet(wb.active)
        >>> len(parsed_rows)
        5
        >>> parsed_rows[0]["land_name"]
        '静岡ススムA1'
        >>> parsed_rows[0]["values"]["ec"]
        0.15
    """
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return [], ["シートにデータがありません。"]

    header_index = None
    header_map = {}
    land_name_column_index = None

    for idx, row in enumerate(rows):
        candidate_map = {}
        candidate_land_index = None
        for col_idx, cell in enumerate(row):
            cell_text = normalize_text(cell or "")
            if not cell_text:
                continue
            if cell_text in NORMALIZED_LAND_NAME_ALIASES:
                candidate_land_index = col_idx
            column_key = CHEMICAL_FIELD_ALIAS_TO_KEY.get(cell_text)
            if not column_key:
                for alias, key in CHEMICAL_FIELD_ALIAS_TO_KEY.items():
                    if alias and alias in cell_text:
                        column_key = key
                        break
            if column_key:
                candidate_map[column_key] = col_idx
        if candidate_land_index is not None and len(candidate_map) >= 1:
            header_index = idx
            header_map = candidate_map
            land_name_column_index = candidate_land_index
            break

    if header_index is None or land_name_column_index is None:
        return [], [
            "ヘッダ行を特定できませんでした。圃場名列と分析項目列を確認してください。"
        ]

    missing = [field for field in CHEMICAL_FIELD_KEYS if field not in header_map]
    if missing:
        return [], [f"必須列不足: {', '.join(missing)}"]

    parsed_rows = []
    parse_errors = []

    for idx in range(header_index + 1, len(rows)):
        row = rows[idx]
        row_number = idx + 1
        land_name_raw = (
            row[land_name_column_index] if land_name_column_index < len(row) else ""
        )
        land_name = str(land_name_raw or "").strip()
        if not land_name:
            continue
        try:
            values = {}
            for field_name, col_idx in header_map.items():
                raw_value = row[col_idx] if col_idx < len(row) else None
                values[field_name] = parse_numeric_value(
                    raw_value, row_number, field_name
                )
            parsed_rows.append(
                {"row_number": row_number, "land_name": land_name, "values": values}
            )
        except ValueError as exc:
            parse_errors.append(str(exc))

    return parsed_rows, parse_errors


class Command(BaseCommand):
    """川田研究所フォーマットのExcelから化学分析データを取り込むDjangoコマンド

    川田研究所が提供する化学分析結果Excel(.xlsx)を読み込み、
    指定されたLandLedgerに紐づけてLandScoreChemicalテーブルにデータを一括登録する。

    1つの圃場データを9ブロック（A1-C3）すべてにコピーする仕様。

    使用方法:
        python manage.py chemical_load_data <excel_path> --land-ledger-id=<id> [--overwrite]

    引数:
        excel_path: 川田研究所のExcelファイルパス（.xlsx）
        --land-ledger-id: 取り込み先のLandLedger ID（必須）
        --overwrite: 既存データを上書きする場合に指定

    動作:
        1. Excelファイルをパースして化学分析データを抽出
        2. 指定されたLandLedgerの存在確認
        3. 必要なLandBlockの存在確認（A1-C3）
        4. トランザクション内でデータを一括登録
           - 既存データがある場合: overwriteならば更新、なければスキップ
           - 新規データ: 作成

    例:
        # 通常の取り込み
        python manage.py chemical_load_data data.xlsx --land-ledger-id=123

        # 既存データを上書き
        python manage.py chemical_load_data data.xlsx --land-ledger-id=123 --overwrite
    """

    help = "Import chemical analysis data from Excel (Kawada format)"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to Excel file (.xlsx)")
        parser.add_argument(
            "--land-ledger-id",
            type=int,
            required=True,
            help="LandLedger ID to associate",
        )
        parser.add_argument(
            "--overwrite", action="store_true", help="Overwrite existing data"
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        land_ledger_id = options["land_ledger_id"]
        overwrite = options.get("overwrite", False)

        try:
            workbook = load_workbook(file_path, data_only=True)
            worksheet = workbook.active
            parsed_rows, parse_errors = parse_kawada_worksheet(worksheet)

            # パースエラーが存在する場合は処理を中断
            if parse_errors:
                for error in parse_errors:
                    self.stderr.write(self.style.ERROR(error))
                return

            # 取り込み対象行が存在しない場合は処理を中断
            if not parsed_rows:
                self.stderr.write(self.style.WARNING("取り込み対象行がありません。"))
                return

            # LandLedgerの存在確認
            try:
                ledger = LandLedger.objects.get(id=land_ledger_id)
            except LandLedger.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"LandLedger ID {land_ledger_id} が見つかりません。"
                    )
                )
                return

            created_count = 0
            updated_count = 0
            warnings = []

            blocks_by_name = {
                b.name: b for b in LandBlock.objects.filter(name__in=BLOCK_NAMES)
            }
            missing_blocks = [
                name for name in BLOCK_NAMES if name not in blocks_by_name
            ]

            if missing_blocks:
                self.stderr.write(
                    self.style.ERROR(f"ブロック不足: {','.join(missing_blocks)}")
                )
                return

            with transaction.atomic():
                for row in parsed_rows:
                    for block_name in BLOCK_NAMES:
                        block = blocks_by_name[block_name]
                        defaults = {**row["values"], "remark": REMARK_IMPORT_MODE}
                        existing = LandScoreChemical.objects.filter(
                            land_ledger=ledger,
                            land_block=block,
                        ).first()

                        if existing:
                            if not overwrite:
                                warnings.append(
                                    f"既存データありスキップ row={row['row_number']}, ledger_id={ledger.id}, block={block_name}"
                                )
                                continue
                            for field_name, field_value in defaults.items():
                                setattr(existing, field_name, field_value)
                            existing.save()
                            updated_count += 1
                            continue

                        LandScoreChemical.objects.create(
                            land_ledger=ledger,
                            land_block=block,
                            **defaults,
                        )
                        created_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"取り込み完了: 新規作成={created_count}, 更新={updated_count}, 警告={len(warnings)}"
                )
            )
            for warning in warnings:
                self.stdout.write(self.style.WARNING(warning))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"エラー: {str(e)}"))
            raise
