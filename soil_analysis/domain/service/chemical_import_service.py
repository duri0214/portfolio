from typing import Any

from django.db import transaction
from django.db.models import Q
from openpyxl.worksheet.worksheet import Worksheet

from soil_analysis.domain.repository.chemical_import_error import (
    ChemicalImportErrorRepository,
)
from soil_analysis.domain.valueobject.management.chemical_import_parser import (
    ChemicalImportParser,
    ChemicalKawadaRow as KawadaRow,
    ChemicalParseResult as ParseResult,
)
from soil_analysis.models import (
    LandLedger,
    Land,
    LandBlock,
    SoilChemicalMeasurement,
)


class ChemicalImportService:
    """
    化学分析データのインポートを管理するサービス
    """

    BLOCK_NAMES = ("A1", "A3", "B2", "C1", "C3")
    KAWADA_FORMAT_DATA_START_ROW_INDEX = 3

    @classmethod
    def parse_kawada_worksheet(cls, worksheet: Worksheet) -> ParseResult:
        """
        川田研究所フォーマットのワークシートをパースする。

        Args:
            worksheet: openpyxl のワークシート

        Returns:
            パース結果（行データとエラーリスト）
        """
        result = ChemicalImportParser.parse_kawada_worksheet(worksheet)
        return ParseResult(rows=result.rows, errors=result.errors)

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
        blocks = LandBlock.objects.filter(name__in=cls.BLOCK_NAMES).values_list(
            "id", flat=True
        )
        if not blocks:
            # 万が一マスタが存在しない場合は、従来のハードコードされた ID をフォールバックとして返す（後方互換性のため）
            return [1, 3, 5, 7, 9]
        return list(blocks)

    @classmethod
    def save_import_data(
        cls, rows_data: list[dict[str, Any]], source_file: str | None = None
    ) -> dict[str, Any]:
        """
        確定済みデータを保存する。
        既存のデータがある場合は上書きし、ない場合は新規作成する。

        Args:
            rows_data: 保存対象のデータリスト（row_data と land_ledger_id を含む）
            source_file: データ元ファイル名

        Returns:
            作成/更新件数やサマリーを含む結果
        """
        created_count = 0
        updated_count = 0
        ledger_stats: dict[int, dict[str, Any]] = {}
        error_count = 0

        ChemicalImportErrorRepository.delete_all()

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
        existing_analyses = SoilChemicalMeasurement.objects.filter(
            land_ledger_id__in=ledger_ids,
        )
        # ledger_id -> record
        existing_map = {m.land_ledger_id: m for m in existing_analyses}

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
                record_values = kawada_row.to_dict()

                existing = existing_map.get(ledger_id)

                if existing:
                    for field_name, field_value in record_values.items():
                        setattr(existing, field_name, field_value)
                    if source_file:
                        existing.source_file = source_file
                    to_update.append(existing)
                    updated_count += 1
                    ledger_stats[ledger_id]["updated"] += 1
                else:
                    new_record = SoilChemicalMeasurement(
                        land_ledger_id=ledger_id,
                        source_file=source_file,
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
                )
                if source_file:
                    update_fields.append("source_file")
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
