from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import unicodedata
from openpyxl.worksheet.worksheet import Worksheet


@dataclass(frozen=True)
class ChemicalKawadaRow:
    """
    川田フォーマットをパースしたデータ行

    Attributes:
        row_number: Excelの行番号
        analysis_number: 分析番号
        person_name: 氏名
        land_name: 圃場名
        crop: 作物
        ec: EC
        ph: pH
        cec: CEC
        cao: 交換性石灰
        mgo: 交換性苦土
        k2o: 交換性加里
        lime_saturation: 石灰飽和度
        magnesia_saturation: 苦土飽和度
        potash_saturation: 加里飽和度
        base_saturation: 塩基飽和度
        p2o5: 可給態リン酸
        phosphorus_absorption: リン酸吸収係数
        nh4n: アンモニア態窒素
        no3n: 硝酸態窒素
        humus: 腐植
        bulk_density: 仮比重
    """

    row_number: int
    analysis_number: int | None
    person_name: str | None = None
    land_name: str = ""
    crop: str | None = None
    ec: float | None = None
    ph: float | None = None
    cec: float | None = None
    cao: float | None = None
    mgo: float | None = None
    k2o: float | None = None
    lime_saturation: float | None = None
    magnesia_saturation: float | None = None
    potash_saturation: float | None = None
    base_saturation: float | None = None
    p2o5: float | None = None
    phosphorus_absorption: float | None = None
    nh4n: float | None = None
    no3n: float | None = None
    humus: float | None = None
    bulk_density: float | None = None

    @staticmethod
    def parse_numeric_value(
        raw_value: object, row_number: int, column_name: str
    ) -> float | None:
        """
        Excelの生の値を数値に変換する。

        Args:
            raw_value: 変換対象の値
            row_number: 行番号（エラーメッセージ用）
            column_name: カラム名（エラーメッセージ用）

        Returns:
            変換後の数値。欠損または変換不能な場合は None

        Raises:
            ValueError: 数値への変換に失敗した場合
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

    @classmethod
    def from_excel_row(cls, row: tuple, row_number: int) -> "ChemicalKawadaRow":
        """
        Excelの1行から ChemicalKawadaRow を生成する。

        Args:
            row: Excelの行データ
            row_number: 行番号

        Returns:
            パースされた ChemicalKawadaRow
        """

        def to_str(col_idx: int) -> str:
            return str(row[col_idx] if col_idx < len(row) else "").strip()

        def to_numeric(col_idx: int, display_name: str) -> float | None:
            raw_value = row[col_idx] if col_idx < len(row) else None
            return cls.parse_numeric_value(raw_value, row_number, display_name)

        raw_analysis_number = cls.parse_numeric_value(row[0], row_number, "分析番号")
        analysis_number = None
        if raw_analysis_number is not None:
            if not float(raw_analysis_number).is_integer():
                raise ValueError(
                    f"分析番号は整数で指定してください row={row_number}, column=分析番号, value={row[0]}"
                )
            analysis_number = int(raw_analysis_number)

        return cls(
            row_number=row_number,
            analysis_number=analysis_number,
            person_name=to_str(1) or None,
            land_name=to_str(2),
            crop=to_str(3) or None,
            ec=to_numeric(4, "EC"),
            ph=to_numeric(5, "pH"),
            cec=to_numeric(6, "CEC"),
            cao=to_numeric(7, "交換性石灰"),
            mgo=to_numeric(8, "交換性苦土"),
            k2o=to_numeric(9, "交換性加里"),
            lime_saturation=to_numeric(10, "石灰飽和度"),
            magnesia_saturation=to_numeric(11, "苦土飽和度"),
            potash_saturation=to_numeric(12, "加里飽和度"),
            base_saturation=to_numeric(13, "塩基飽和度"),
            p2o5=to_numeric(14, "可給態リン酸"),
            phosphorus_absorption=to_numeric(15, "リン酸吸収係数"),
            nh4n=to_numeric(16, "アンモニア態窒素"),
            no3n=to_numeric(17, "硝酸態窒素"),
            humus=to_numeric(18, "腐植"),
            bulk_density=to_numeric(19, "仮比重"),
        )

    def to_dict(self) -> dict[str, float | None]:
        """
        モデル保存用の辞書形式に変換する。

        Returns:
            フィールド名をキーとする辞書
        """
        return {
            "analysis_number": self.analysis_number,
            "ec": self.ec,
            "nh4n": self.nh4n,
            "no3n": self.no3n,
            "ph": self.ph,
            "cao": self.cao,
            "mgo": self.mgo,
            "k2o": self.k2o,
            "lime_saturation": self.lime_saturation,
            "magnesia_saturation": self.magnesia_saturation,
            "potash_saturation": self.potash_saturation,
            "base_saturation": self.base_saturation,
            "phosphorus_absorption": self.phosphorus_absorption,
            "p2o5": self.p2o5,
            "cec": self.cec,
            "humus": self.humus,
            "bulk_density": self.bulk_density,
        }


@dataclass(frozen=True)
class ChemicalParseResult:
    """
    Excelパース結果を保持するクラス

    Attributes:
        rows: パースされた ChemicalKawadaRow のリスト
        errors: パース中に発生したエラーメッセージのリスト
    """

    rows: list[ChemicalKawadaRow]
    errors: list[str]


class ChemicalImportParser:
    """
    川田研究所フォーマットのExcelシートを解析するパーサ
    """

    KAWADA_FORMAT_DATA_START_ROW_INDEX = 3

    @classmethod
    def parse_kawada_worksheet(cls, worksheet: Worksheet) -> ChemicalParseResult:
        """
        川田研究所フォーマットのワークシートをパースする。

        Args:
            worksheet: openpyxl のワークシート

        Returns:
            パース結果（行データとエラーリスト）
        """
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            return ChemicalParseResult(rows=[], errors=["シートにデータがありません。"])

        if len(rows) <= 2:  # Header is at index 2
            return ChemicalParseResult(
                rows=[], errors=["ヘッダー行に満たない行数でした。"]
            )

        parsed_rows = []
        parse_errors = []

        for i in range(cls.KAWADA_FORMAT_DATA_START_ROW_INDEX, len(rows)):
            row = rows[i]
            row_number = i + 1

            analysis_number_raw = row[0] if len(row) > 0 else ""
            analysis_number = str(analysis_number_raw or "").strip()
            if not analysis_number:
                continue

            try:
                parsed_rows.append(ChemicalKawadaRow.from_excel_row(row, row_number))
            except ValueError as exc:
                parse_errors.append(f"row={row_number}: {exc}")

        return ChemicalParseResult(rows=parsed_rows, errors=parse_errors)
