from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import unicodedata
from django.db import transaction
from openpyxl.worksheet.worksheet import Worksheet

from soil_analysis.models import (
    LandLedger,
    SoilChemicalMeasurement,
    Land,
    SoilChemicalMeasurementImportErrors,
)


@dataclass(frozen=True)
class KawadaRow:
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
    analysis_number: str
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
    def to_float(raw_value: object, row_number: int, column_name: str) -> float | None:
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

        def to_numeric(col_idx: int, display_name: str) -> float | None:
            raw_value = row[col_idx] if col_idx < len(row) else None
            return cls.to_float(raw_value, row_number, display_name)

        return cls(
            row_number=row_number,
            analysis_number=to_str(0),
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
    """
    Excelパース結果を保持するクラス

    Attributes:
        rows: パースされた KawadaRow のリスト
        errors: パース中に発生したエラーメッセージのリスト
    """

    rows: list[KawadaRow]
    errors: list[str]


class ChemicalImportService:
    BLOCK_NAMES = ("A1", "A3", "B2", "C1", "C3")
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
        cls, land_name: str, base_ledger_id: int | None = None
    ) -> list[LandLedger]:
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

                # 同じ period のものを優先的に並び替える
                def sort_key(l):
                    return (
                        0 if l.land_period_id == base_ledger.land_period_id else 1,
                        l.id,
                    )

                ledgers = sorted(ledgers, key=sort_key)
            except LandLedger.DoesNotExist:
                pass

        return list(ledgers[:10])  # とりあえず上位10件

    @classmethod
    def get_suggested_ledgers_for_names(
        cls, land_names: list[str], base_ledger_id: int | None = None
    ) -> dict[str, list[LandLedger]]:
        """
        複数の圃場名に対して候補となる帳簿を一括取得する。
        """
        from django.db.models import Q

        if not land_names:
            return {}

        query = Q()
        for name in set(land_names):
            if name:
                query |= Q(name__icontains=name)

        if not query:
            return {name: [] for name in land_names}

        lands = Land.objects.filter(query)
        all_ledgers = list(
            LandLedger.objects.filter(land__in=lands)
            .select_related("land", "land__company", "land_period")
            .order_by("-id")
        )

        base_period_id = None
        if base_ledger_id:
            try:
                base_period_id = LandLedger.objects.values_list(
                    "land_period_id", flat=True
                ).get(id=base_ledger_id)
            except LandLedger.DoesNotExist:
                pass

        result = {}
        for name in land_names:
            # 各名称に合致するものを抽出（メモリ上でフィルタリング）
            suggested = [l for l in all_ledgers if name.lower() in l.land.name.lower()]

            if base_period_id:

                def sort_key(l):
                    return 0 if l.land_period_id == base_period_id else 1

                suggested.sort(key=sort_key)

            result[name] = suggested[:10]

        return result

    @classmethod
    def _get_block_ids(cls) -> list[int]:
        """
        BLOCK_NAMES に合致する LandBlock の ID リストを取得する。
        """
        from soil_analysis.models import LandBlock

        blocks = LandBlock.objects.filter(name__in=cls.BLOCK_NAMES).values_list(
            "id", flat=True
        )
        if not blocks:
            # 万が一マスタが存在しない場合は、従来のハードコードされた ID をフォールバックとして返す（後方互換性のため）
            return [1, 3, 5, 7, 9]
        return list(blocks)

    @classmethod
    def save_import_data(cls, rows_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        確定済みデータを保存する
        rows_data: [
            {
                "row_data": {...}, # KawadaRow を dict にしたもの
                "land_ledger_id": 123
            },
        ]
        """
        created_count = 0
        updated_count = 0
        ledger_stats: dict[int, dict[str, Any]] = {}
        error_count = 0

        SoilChemicalMeasurementImportErrors.objects.all().delete()

        # 同一取り込み内で同じ帳簿が複数行に割り当たっている場合は、後のものを優先する（上書き許容）
        ledger_to_latest_entry: dict[int, dict[str, Any]] = {}
        for entry in rows_data:
            ledger_id = entry.get("land_ledger_id")
            if not ledger_id:
                continue
            ledger_to_latest_entry[ledger_id] = entry

        valid_entries = list(ledger_to_latest_entry.values())
        ledger_ids = [e["land_ledger_id"] for e in valid_entries]

        if not ledger_ids:
            return {
                "created": 0,
                "updated": 0,
                "ledger_summary": [],
                "ledger_ids": [],
                "error_count": error_count,
            }

        # 既存レコードを一括取得
        block_ids = cls._get_block_ids()
        existing_measurements = SoilChemicalMeasurement.objects.filter(
            land_ledger_id__in=ledger_ids,
            land_block_id__in=block_ids,
        )
        # (ledger_id, block_id) -> record
        existing_map = {
            (m.land_ledger_id, m.land_block_id): m for m in existing_measurements
        }

        ledgers_map = {
            l.id: l
            for l in LandLedger.objects.filter(id__in=ledger_ids).select_related(
                "land", "land__company", "land_period"
            )
        }

        to_create = []
        to_update = []

        with transaction.atomic():
            for entry in valid_entries:
                ledger_id = entry["land_ledger_id"]
                ledger = ledgers_map.get(ledger_id)
                if not ledger:
                    continue

                row_dict = entry["row_data"]
                if ledger_id not in ledger_stats:
                    ledger_stats[ledger_id] = {
                        "ledger": ledger,
                        "created": 0,
                        "updated": 0,
                    }

                kawada_row = KawadaRow(**row_dict)
                record_values = {
                    **kawada_row.to_dict(),
                    "remark": cls.REMARK_IMPORT_MODE,
                }

                for block_id in block_ids:
                    existing = existing_map.get((ledger_id, block_id))

                    if existing:
                        for field_name, field_value in record_values.items():
                            setattr(existing, field_name, field_value)
                        to_update.append(existing)
                        updated_count += 1
                        ledger_stats[ledger_id]["updated"] += 1
                    else:
                        new_record = SoilChemicalMeasurement(
                            land_ledger_id=ledger_id,
                            land_block_id=block_id,
                            **record_values,
                        )
                        to_create.append(new_record)
                        created_count += 1
                        ledger_stats[ledger_id]["created"] += 1

            if to_create:
                SoilChemicalMeasurement.objects.bulk_create(to_create)
            if to_update:
                # 更新対象のフィールドを動的に取得（to_dict のキー + remark）
                update_fields = list(
                    KawadaRow(**valid_entries[0]["row_data"]).to_dict().keys()
                ) + ["remark"]
                SoilChemicalMeasurement.objects.bulk_update(to_update, update_fields)

        summary = []
        for stat in ledger_stats.values():
            ledger = stat["ledger"]
            summary.append(
                {
                    "company_name": ledger.land.company.name,
                    "land_name": ledger.land.name,
                    "period_name": ledger.land_period.name,
                    "sampling_date": (
                        ledger.sampling_date.isoformat()
                        if ledger.sampling_date
                        else None
                    ),
                    "created": stat["created"],
                    "updated": stat["updated"],
                    "total": stat["created"] + stat["updated"],
                }
            )

        return {
            "created": created_count,
            "updated": updated_count,
            "ledger_summary": summary,
            "ledger_ids": list(ledger_stats.keys()),
            "error_count": error_count,
        }
