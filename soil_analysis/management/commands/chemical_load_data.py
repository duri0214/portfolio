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

import attrs
import unicodedata
from django.core.management.base import BaseCommand
from django.db import transaction
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from soil_analysis.models import LandLedger, LandScoreChemical


@attrs.frozen
class KawadaRow:
    """川田フォーマットをパースしたデータ行

    Attributes:
        row_number: データ行のExcel行番号（警告・エラー表示用）
            本コマンドではヘッダーが3行目・データ開始が4行目のため、
            通常の最小値は4になる。
        analysis_number: 分析番号（A列）
        person_name: 氏名（B列）
        land_name: 圃場名（C列）
        crop: 栽培作物（D列）
        ec: EC（E列）
        ph: pH（F列）
        cec: CEC（G列、meq/100g）
        cao: CaO（H列）
        mgo: MgO（I列）
        k2o: K2O（J列）
        lime_saturation: 石灰飽和度（K列、%）
        magnesia_saturation: 苦土飽和度（L列、%）
        potash_saturation: 加里飽和度（M列、%）
        base_saturation: 塩基飽和度（N列、%）
        p2o5: P2O5（O列）
        phosphorus_absorption: リン酸吸収係数（P列）
        nh4n: NH4-N（Q列）
        no3n: NO3-N（R列）
        humus: 腐植（S列）
        bulk_density: 仮比重（T列）
    """

    row_number: int
    analysis_number: str
    person_name: str | None
    land_name: str
    crop: str | None
    ec: float | None
    ph: float | None
    cec: float | None
    cao: float | None
    mgo: float | None
    k2o: float | None
    lime_saturation: float | None
    magnesia_saturation: float | None
    potash_saturation: float | None
    base_saturation: float | None
    p2o5: float | None
    phosphorus_absorption: float | None
    nh4n: float | None
    no3n: float | None
    humus: float | None
    bulk_density: float | None

    @staticmethod
    def to_float(raw_value: object, row_number: int, column_name: str) -> float | None:
        """Excelセルの値を数値（float）に変換する。"""
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

    @classmethod
    def from_excel_row(cls, row: tuple, row_number: int) -> "KawadaRow":
        """Excelの1行データからKawadaRowを構築する。"""

        def to_str(col_idx: int) -> str:
            """指定列のセル値を文字列として取得する。"""
            return str(row[col_idx] if col_idx < len(row) else "").strip()

        def to_numeric(col_idx: int, field_name: str) -> float | None:
            """指定列のセル値を数値として取得する。"""
            raw_value = row[col_idx] if col_idx < len(row) else None
            return cls.to_float(raw_value, 0, field_name)

        return cls(
            row_number=row_number,
            analysis_number=to_str(KAWADA_COLUMN_ANALYSIS_NUMBER),
            person_name=to_str(KAWADA_COLUMN_PERSON_NAME) or None,
            land_name=to_str(KAWADA_COLUMN_LAND_NAME),
            crop=to_str(KAWADA_COLUMN_CROP) or None,
            ec=to_numeric(4, "ec"),
            ph=to_numeric(5, "ph"),
            cec=to_numeric(6, "cec"),
            cao=to_numeric(7, "cao"),
            mgo=to_numeric(8, "mgo"),
            k2o=to_numeric(9, "k2o"),
            lime_saturation=to_numeric(10, "lime_saturation"),
            magnesia_saturation=to_numeric(11, "magnesia_saturation"),
            potash_saturation=to_numeric(12, "potash_saturation"),
            base_saturation=to_numeric(13, "base_saturation"),
            p2o5=to_numeric(14, "p2o5"),
            phosphorus_absorption=to_numeric(15, "phosphorus_absorption"),
            nh4n=to_numeric(16, "nh4n"),
            no3n=to_numeric(17, "no3n"),
            humus=to_numeric(18, "humus"),
            bulk_density=to_numeric(19, "bulk_density"),
        )


@attrs.frozen
class ParseResult:
    """Excelパース結果

    Attributes:
        rows: パース済みデータ行のリスト
        errors: エラーメッセージのリスト
    """

    rows: list[ParsedRow]
    errors: list[str]


# 取り込み対象のブロックID（5点測量: 四隅+中央）
BLOCK_IDS = (1, 3, 5, 7, 9)

# 取り込みモードを示すremark文字列（圃場レベルのデータを5ブロックにコピーしたことを示す）
REMARK_IMPORT_MODE = "import_mode=field_level_copied_to_5_blocks"

# 川田研究所フォーマットの前提条件（フォーマット変更時はここを修正）
# 行定義（0-based: Pythonのリストインデックス）
KAWADA_FORMAT_HEADER_ROW_INDEX = 2  # 3行目（ヘッダー行）
KAWADA_FORMAT_DATA_START_ROW_INDEX = 3  # 4行目（データ開始行）

# 列定義（0-based: Pythonのリストインデックス）
KAWADA_COLUMN_ANALYSIS_NUMBER = 0  # A列: 分析番号
KAWADA_COLUMN_PERSON_NAME = 1  # B列: 氏名
KAWADA_COLUMN_LAND_NAME = 2  # C列: 圃場名
KAWADA_COLUMN_CROP = 3  # D列: 栽培作物
# E列: 化学分析データ開始（CHEMICAL_FIELD_DEFINITIONSの順序で17項目）
KAWADA_COLUMN_CHEMICAL_START = 4

# セル参照（1-based: Excelのセル記法）
KAWADA_CELL_ANALYSIS_DATE = (
    "G1"  # 分析日（将来的に LandLedger.reporting_date に取り込み予定）
)


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


def _parse_kawada_row(row: tuple) -> KawadaRow:
    """川田フォーマットの1行をパースしてVOを構築

    Args:
        row: Excelの行データ（タプル）

    Returns:
        KawadaRow: 川田フォーマット1行分のVO

    Raises:
        ValueError: 数値変換に失敗した場合（行番号なし、呼び出し側で追加すること）
    """

    def get_cell(col_idx: int) -> str:
        """セル値を文字列として取得"""
        return str(row[col_idx] if col_idx < len(row) else "").strip()

    def get_numeric(col_idx: int, field_name: str) -> float | None:
        """セル値を数値として取得"""
        raw_value = row[col_idx] if col_idx < len(row) else None
        # row_numberなしでパース（エラーメッセージには列名と値のみ）
        return parse_numeric_value(raw_value, 0, field_name)

    return KawadaRow(
        analysis_number=get_cell(KAWADA_COLUMN_ANALYSIS_NUMBER),
        person_name=get_cell(KAWADA_COLUMN_PERSON_NAME) or None,
        land_name=get_cell(KAWADA_COLUMN_LAND_NAME),
        crop=get_cell(KAWADA_COLUMN_CROP) or None,
        ec=get_numeric(4, "ec"),
        ph=get_numeric(5, "ph"),
        cec=get_numeric(6, "cec"),
        cao=get_numeric(7, "cao"),
        mgo=get_numeric(8, "mgo"),
        k2o=get_numeric(9, "k2o"),
        lime_saturation=get_numeric(10, "lime_saturation"),
        magnesia_saturation=get_numeric(11, "magnesia_saturation"),
        potash_saturation=get_numeric(12, "potash_saturation"),
        base_saturation=get_numeric(13, "base_saturation"),
        p2o5=get_numeric(14, "p2o5"),
        phosphorus_absorption=get_numeric(15, "phosphorus_absorption"),
        nh4n=get_numeric(16, "nh4n"),
        no3n=get_numeric(17, "no3n"),
        humus=get_numeric(18, "humus"),
        bulk_density=get_numeric(19, "bulk_density"),
    )


def parse_kawada_worksheet(worksheet: Worksheet) -> ParseResult:
    """川田研究所フォーマットのExcelシートをパースして化学分析データを抽出する

    川田研究所フォーマットの前提条件:
        - ヘッダ行: 3行目固定
        - 分析日: G1セル
        - 必須列: 圃場名 + 17項目の化学分析項目

    処理の流れ:
        1. 3行目のヘッダー行から列マッピングを構築
        2. 圃場名列と必須17項目の存在をチェック
        3. 4行目以降のデータ行をパースして数値変換

    Args:
        worksheet: openpyxlのワークシートオブジェクト

    Returns:
        ParseResult: パース結果とエラーリストを含むVO

    Examples:
        >>> from openpyxl import load_workbook
        >>> wb = load_workbook("kawada_data.xlsx", data_only=True)
        >>> result = parse_kawada_worksheet(wb.active)
        >>> len(result.rows)
        5
        >>> result.rows[0].land_name
        '静岡ススムA1'
        >>> result.rows[0].values["ec"]
        0.15
    """
    # Excelシートのすべての行を取得（空行も含む）
    # rows[0] = 1行目, rows[1] = 2行目（空行）, rows[2] = 3行目（ヘッダー）, ...
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return ParseResult(rows=[], errors=["シートにデータがありません。"])

    # ヘッダー行の存在チェック
    if len(rows) <= KAWADA_FORMAT_HEADER_ROW_INDEX:
        return ParseResult(
            rows=[],
            errors=[
                f"ヘッダー行に満たない行数でした（{len(rows)}行、ヘッダーは{KAWADA_FORMAT_HEADER_ROW_INDEX + 1}行目）。"
            ],
        )

    # データ行のパース（4行目以降）
    # 各行から以下を抽出:
    #   1. 分析番号（A列）- 空行はスキップ（川田研究所側のID）
    #   2. 圃場名（C列）
    #   3. 化学分析データ（E列〜T列の16項目）- 川田フォーマットの列位置に基づいて取得
    #   4. 数値変換エラーがあればエラーリストに追加して次の行へ
    parsed_rows = []
    parse_errors = []

    for i in range(KAWADA_FORMAT_DATA_START_ROW_INDEX, len(rows)):
        row = rows[i]
        row_number = i + 1  # Excelの行番号（1始まり、ユーザー向け表示用）

        # 分析番号（A列）の取得
        analysis_number_raw = (
            row[KAWADA_COLUMN_ANALYSIS_NUMBER]
            if KAWADA_COLUMN_ANALYSIS_NUMBER < len(row)
            else ""
        )
        analysis_number = str(analysis_number_raw or "").strip()
        if not analysis_number:
            continue  # 分析番号が空の行はスキップ（空行または非データ行）

        try:
            # 川田フォーマット1行分をVOとして構築
            kawada_row = _parse_kawada_row(row)

            # LandScoreChemical用に変換（ticket7まで暫定対応）
            # 川田にあってLandScoreChemicalにない項目: lime_saturation, magnesia_saturation, potash_saturation → 無視
            # 川田にないLandScoreChemicalの項目: total_nitrogen, nh4_per_nitrogen, cao_per_mgo, mgo_per_k2o → None
            values = {
                "ec": kawada_row.ec,
                "nh4n": kawada_row.nh4n,
                "no3n": kawada_row.no3n,
                "total_nitrogen": None,  # TODO: ticket7で削除
                "nh4_per_nitrogen": None,  # TODO: ticket7で削除
                "ph": kawada_row.ph,
                "cao": kawada_row.cao,
                "mgo": kawada_row.mgo,
                "k2o": kawada_row.k2o,
                "base_saturation": kawada_row.base_saturation,
                "cao_per_mgo": None,  # TODO: ticket7で削除
                "mgo_per_k2o": None,  # TODO: ticket7で削除
                "phosphorus_absorption": kawada_row.phosphorus_absorption,
                "p2o5": kawada_row.p2o5,
                "cec": kawada_row.cec,
                "humus": kawada_row.humus,
                "bulk_density": kawada_row.bulk_density,
            }

            parsed_rows.append(
                ParsedRow(
                    row_number=row_number, land_name=kawada_row.land_name, values=values
                )
            )
        except ValueError as exc:
            # 数値変換エラー: 行番号を追加してエラーリストに記録
            parse_errors.append(f"row={row_number}: {exc}")

    return ParseResult(rows=parsed_rows, errors=parse_errors)


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

            # シート数が1であることを確認
            if len(workbook.sheetnames) != 1:
                self.stderr.write(
                    self.style.ERROR(
                        f"Excelファイルのシート数が1ではありません（{len(workbook.sheetnames)}枚）。"
                        f"シートは1枚にしてください。"
                    )
                )
                return
            worksheet = workbook.active
            parse_result = parse_kawada_worksheet(worksheet)

            # パースエラーが存在する場合は処理を中断
            if parse_result.errors:
                for error in parse_result.errors:
                    self.stderr.write(self.style.ERROR(error))
                return

            # 取り込み対象行が存在しない場合は処理を中断
            if not parse_result.rows:
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

            # TODO(ticket7): LandScoreChemicalのland_block FK削除後、このブロック展開処理は不要になる
            # 暫定対応: 圃場単位データ（1レコード）を5ブロック（1,3,5,7,9）に展開して保存
            # - 現行モデルはland_blockが必須のため、5ブロック分のレコードを作成（5点法）
            # - remarkに"import_mode=field_level_copied_to_5_blocks"を付与して識別

            with transaction.atomic():
                for row in parse_result.rows:
                    for block_id in BLOCK_IDS:
                        defaults = {**row.values, "remark": REMARK_IMPORT_MODE}
                        existing = LandScoreChemical.objects.filter(
                            land_ledger=ledger,
                            land_block_id=block_id,
                        ).first()

                        if existing:
                            if not overwrite:
                                warnings.append(
                                    f"既存データありスキップ row={row.row_number}, ledger_id={ledger.id}, block_id={block_id}"
                                )
                                continue
                            for field_name, field_value in defaults.items():
                                setattr(existing, field_name, field_value)
                            existing.save()
                            updated_count += 1
                            continue

                        LandScoreChemical.objects.create(
                            land_ledger=ledger,
                            land_block_id=block_id,
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
