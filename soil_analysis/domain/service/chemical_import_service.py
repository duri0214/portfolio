from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Any

import unicodedata
from django.db import transaction
from openpyxl.worksheet.worksheet import Worksheet

from soil_analysis.models import LandLedger, LandScoreChemical, Land


@dataclass(frozen=True)
class KawadaRow:
    """川田フォーマットをパースしたデータ行"""

    row_number: int
    analysis_number: str
    person_name: Optional[str]
    land_name: str
    crop: Optional[str]
    ec: Optional[float]
    ph: Optional[float]
    cec: Optional[float]
    cao: Optional[float]
    mgo: Optional[float]
    k2o: Optional[float]
    lime_saturation: Optional[float]
    magnesia_saturation: Optional[float]
    potash_saturation: Optional[float]
    base_saturation: Optional[float]
    p2o5: Optional[float]
    phosphorus_absorption: Optional[float]
    nh4n: Optional[float]
    no3n: Optional[float]
    humus: Optional[float]
    bulk_density: Optional[float]

    @staticmethod
    def to_float(
        raw_value: object, row_number: int, column_name: str
    ) -> Optional[float]:
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
        def to_str(col_idx: int) -> str:
            return str(row[col_idx] if col_idx < len(row) else "").strip()

        def to_numeric(col_idx: int, field_name: str) -> Optional[float]:
            raw_value = row[col_idx] if col_idx < len(row) else None
            return cls.to_float(raw_value, row_number, field_name)

        return cls(
            row_number=row_number,
            analysis_number=to_str(0),
            person_name=to_str(1) or None,
            land_name=to_str(2),
            crop=to_str(3) or None,
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

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "ec": self.ec,
            "nh4n": self.nh4n,
            "no3n": self.no3n,
            "total_nitrogen": None,
            "nh4_per_nitrogen": None,
            "ph": self.ph,
            "cao": self.cao,
            "mgo": self.mgo,
            "k2o": self.k2o,
            "base_saturation": self.base_saturation,
            "cao_per_mgo": None,
            "mgo_per_k2o": None,
            "phosphorus_absorption": self.phosphorus_absorption,
            "p2o5": self.p2o5,
            "cec": self.cec,
            "humus": self.humus,
            "bulk_density": self.bulk_density,
        }


@dataclass(frozen=True)
class ParseResult:
    rows: List[KawadaRow]
    errors: List[str]


class ChemicalImportService:
    BLOCK_IDS = (1, 3, 5, 7, 9)
    REMARK_IMPORT_MODE = "import_mode=field_level_copied_to_5_blocks"
    KAWADA_FORMAT_DATA_START_ROW_INDEX = 3

    @classmethod
    def parse_kawada_worksheet(cls, worksheet: Worksheet) -> ParseResult:
        rows = list(worksheet.iter_rows(values_only=True))
        if not rows:
            return ParseResult(rows=[], errors=["シートにデータがありません。"])

        if len(rows) <= 2:  # Header is at index 2
            return ParseResult(rows=[], errors=["ヘッダー行に満たない行数でした。"])

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
                parsed_rows.append(KawadaRow.from_excel_row(row, row_number))
            except ValueError as exc:
                parse_errors.append(f"row={row_number}: {exc}")

        return ParseResult(rows=parsed_rows, errors=parse_errors)

    @classmethod
    def get_suggested_ledgers(
        cls, land_name: str, base_ledger_id: Optional[int] = None
    ) -> List[LandLedger]:
        """
        圃場名から候補となる帳簿を検索する。
        base_ledger_id が指定されている場合、その帳簿と同じ period を持つものを優先する。
        """
        # 圃場名で検索（完全一致または部分一致）
        lands = Land.objects.filter(name__icontains=land_name)

        # それらの圃場に紐づく帳簿を取得
        ledgers = LandLedger.objects.filter(land__in=lands).select_related(
            "land", "land__company", "land_period"
        )

        if base_ledger_id:
            try:
                base_ledger = LandLedger.objects.get(id=base_ledger_id)

                # 同じ period のものを優先的に並び替える（本当はもっと複雑なロジックが必要かもしれないが、まずは単純に）
                # ここでは Django の並び替えではなく Python 側で行う
                def sort_key(l):
                    return (
                        0 if l.land_period_id == base_ledger.land_period_id else 1,
                        l.id,
                    )

                ledgers = sorted(ledgers, key=sort_key)
            except LandLedger.DoesNotExist:
                pass

        return ledgers[:10]  # とりあえず上位10件

    @classmethod
    def save_import_data(
        cls, rows_data: List[Dict[str, Any]], overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        確定済みデータを保存する
        rows_data: [
            {
                "row_data": {...}, # KawadaRow を dict にしたもの
                "land_ledger_id": 123
            },
            ...
        ]
        """
        created_count = 0
        updated_count = 0
        skipped_count = 0
        ledger_stats: Dict[int, Dict[str, Any]] = {}

        with transaction.atomic():
            for entry in rows_data:
                ledger_id = entry.get("land_ledger_id")
                if not ledger_id:
                    continue

                ledger = LandLedger.objects.get(id=ledger_id)
                row_dict = entry["row_data"]
                if ledger.id not in ledger_stats:
                    ledger_stats[ledger.id] = {
                        "ledger": ledger,
                        "created": 0,
                        "updated": 0,
                    }

                # KawadaRow.to_dict 相当のデータを作成
                # ただし row_dict は KawadaRow 全体の dict なので、分析値の部分だけ抽出が必要
                # 簡略化のため、KawadaRow インスタンスを再構成して to_dict を呼ぶ
                kawada_row = KawadaRow(**row_dict)
                record_values = {
                    **kawada_row.to_dict(),
                    "remark": cls.REMARK_IMPORT_MODE,
                }

                for block_id in cls.BLOCK_IDS:
                    existing = LandScoreChemical.objects.filter(
                        land_ledger=ledger,
                        land_block_id=block_id,
                    ).first()

                    if existing:
                        if not overwrite:
                            skipped_count += 1
                            continue
                        for field_name, field_value in record_values.items():
                            setattr(existing, field_name, field_value)
                        existing.save()
                        updated_count += 1
                        ledger_stats[ledger.id]["updated"] += 1
                        continue

                    LandScoreChemical.objects.create(
                        land_ledger=ledger,
                        land_block_id=block_id,
                        **record_values,
                    )
                    created_count += 1
                    ledger_stats[ledger.id]["created"] += 1

        summary = []
        for stat in ledger_stats.values():
            ledger = stat["ledger"]
            summary.append(
                {
                    "company_name": ledger.land.company.name,
                    "land_name": ledger.land.name,
                    "period_name": ledger.land_period.name,
                    "sampling_date": ledger.sampling_date.isoformat()
                    if ledger.sampling_date
                    else None,
                    "created": stat["created"],
                    "updated": stat["updated"],
                    "total": stat["created"] + stat["updated"],
                }
            )

        return {
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "ledger_summary": summary,
            "ledger_ids": list(ledger_stats.keys()),
        }
