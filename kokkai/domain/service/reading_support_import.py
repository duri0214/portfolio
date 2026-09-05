from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import TextIO

from django.core.exceptions import ValidationError
from django.db import transaction

from ...models import ReadingSupportEntry
from ..valueobject.reading_support import normalize_surface


@dataclass(frozen=True)
class ReadingSupportImportError:
    """CSVの1行に対する検証エラー。"""

    line_number: int
    message: str


@dataclass(frozen=True)
class ReadingSupportImportResult:
    """CSV取り込みの件数とエラーを表す結果。"""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: tuple[ReadingSupportImportError, ...] = ()

    @property
    def is_success(self) -> bool:
        return not self.errors


class ReadingSupportCsvImporter:
    """用語・読み補正CSVを検証して辞書へ取り込む。"""

    REQUIRED_COLUMNS = (
        "surface",
        "reading",
        "description",
        "category",
        "source_url",
    )
    OPTIONAL_COLUMNS = ("entry_type", "is_active")
    _ENTRY_TYPE_ALIASES = {
        "term": ReadingSupportEntry.EntryType.TERM,
        "用語": ReadingSupportEntry.EntryType.TERM,
        "reading_override": ReadingSupportEntry.EntryType.READING_OVERRIDE,
        "reading-override": ReadingSupportEntry.EntryType.READING_OVERRIDE,
        "override": ReadingSupportEntry.EntryType.READING_OVERRIDE,
        "読み補正": ReadingSupportEntry.EntryType.READING_OVERRIDE,
    }
    _TRUE_VALUES = {"1", "true", "yes", "on", "有効", "はい"}
    _FALSE_VALUES = {"0", "false", "no", "off", "無効", "いいえ"}

    def import_csv(
        self,
        source: bytes | str | TextIO,
        *,
        update_existing: bool = False,
    ) -> ReadingSupportImportResult:
        """CSV全体を検証し、エラーがなければ一括保存する。"""
        try:
            csv_text = self._decode_source(source)
        except UnicodeDecodeError:
            return ReadingSupportImportResult(
                errors=(
                    ReadingSupportImportError(
                        line_number=1,
                        message="CSVはUTF-8で保存してください。",
                    ),
                )
            )

        reader = csv.DictReader(io.StringIO(csv_text, newline=""))
        fieldnames = [field.strip() for field in (reader.fieldnames or [])]
        missing_columns = [
            column for column in self.REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing_columns:
            return ReadingSupportImportResult(
                errors=(
                    ReadingSupportImportError(
                        line_number=1,
                        message=(
                            "必須列が不足しています: " + ", ".join(missing_columns)
                        ),
                    ),
                )
            )

        entries_to_save: list[tuple[ReadingSupportEntry, bool]] = []
        errors: list[ReadingSupportImportError] = []
        seen_surfaces: set[str] = set()
        skipped = 0

        for row in reader:
            line_number = reader.line_num
            if self._is_empty_row(row):
                continue
            try:
                values = self._row_values(row)
                entry = self._build_entry(values)
                normalized_surface = entry.normalized_surface
                if normalized_surface in seen_surfaces:
                    raise ValueError("同じCSV内に同じ表記が複数あります。")
                seen_surfaces.add(normalized_surface)

                existing = ReadingSupportEntry.objects.filter(
                    normalized_surface=normalized_surface
                ).first()
                if existing is not None:
                    if self._same_values(existing, entry):
                        skipped += 1
                        continue
                    if not update_existing:
                        raise ValueError(
                            "既存データと異なるため更新できません。"
                            "更新する場合は --update-existing を指定してください。"
                        )
                    self._copy_values(entry, existing)
                    existing.full_clean()
                    entries_to_save.append((existing, False))
                else:
                    entry.full_clean()
                    entries_to_save.append((entry, True))
            except (ValidationError, ValueError) as error:
                errors.append(
                    ReadingSupportImportError(
                        line_number=line_number,
                        message=self._error_message(error),
                    )
                )

        if errors:
            return ReadingSupportImportResult(errors=tuple(errors))

        created = 0
        updated = 0
        with transaction.atomic():
            for entry, is_new in entries_to_save:
                entry.save()
                if is_new:
                    created += 1
                else:
                    updated += 1
        return ReadingSupportImportResult(
            created=created,
            updated=updated,
            skipped=skipped,
        )

    @staticmethod
    def _decode_source(source: bytes | str | TextIO) -> str:
        if isinstance(source, bytes):
            return source.decode("utf-8-sig")
        if isinstance(source, str):
            return source
        value = source.read()
        if isinstance(value, bytes):
            return value.decode("utf-8-sig")
        return value

    @staticmethod
    def _is_empty_row(row: dict[str | None, str | list[str] | None]) -> bool:
        for value in row.values():
            if isinstance(value, list):
                if any(item.strip() for item in value if item):
                    return False
            elif value and value.strip():
                return False
        return True

    @staticmethod
    def _row_values(row: dict[str | None, str | list[str] | None]) -> dict[str, str]:
        if None in row and row[None]:
            raise ValueError("列数がヘッダーと一致しません。")
        return {
            str(key).strip(): (value or "").strip()
            for key, value in row.items()
            if key is not None
        }

    def _build_entry(self, values: dict[str, str]) -> ReadingSupportEntry:
        surface = values.get("surface", "")
        reading = values.get("reading", "")
        description = values.get("description", "")
        category = values.get("category", "")
        source_url = values.get("source_url", "")
        raw_entry_type = values.get("entry_type", "").casefold()
        if raw_entry_type:
            entry_type = self._ENTRY_TYPE_ALIASES.get(raw_entry_type)
            if entry_type is None:
                raise ValueError(
                    "entry_type は term または reading_override を指定してください。"
                )
        else:
            entry_type = (
                ReadingSupportEntry.EntryType.READING_OVERRIDE
                if not any((description, category, source_url))
                else ReadingSupportEntry.EntryType.TERM
            )

        is_active = self._parse_is_active(values.get("is_active", ""))
        return ReadingSupportEntry(
            entry_type=entry_type,
            surface=surface,
            normalized_surface=normalize_surface(surface),
            reading=reading,
            description=description,
            category=category,
            source_url=source_url,
            is_active=is_active,
        )

    @classmethod
    def _parse_is_active(cls, value: str) -> bool:
        if not value:
            return True
        normalized = value.casefold()
        if normalized in cls._TRUE_VALUES:
            return True
        if normalized in cls._FALSE_VALUES:
            return False
        raise ValueError("is_active は true または false を指定してください。")

    @staticmethod
    def _copy_values(source: ReadingSupportEntry, target: ReadingSupportEntry) -> None:
        target.entry_type = source.entry_type
        target.surface = source.surface
        target.normalized_surface = source.normalized_surface
        target.reading = source.reading
        target.description = source.description
        target.category = source.category
        target.source_url = source.source_url
        target.is_active = source.is_active

    @staticmethod
    def _same_values(left: ReadingSupportEntry, right: ReadingSupportEntry) -> bool:
        return all(
            getattr(left, field) == getattr(right, field)
            for field in (
                "entry_type",
                "surface",
                "normalized_surface",
                "reading",
                "description",
                "category",
                "source_url",
                "is_active",
            )
        )

    @staticmethod
    def _error_message(error: ValidationError | ValueError) -> str:
        if isinstance(error, ValidationError):
            if hasattr(error, "message_dict"):
                messages = [
                    message
                    for field_messages in error.message_dict.values()
                    for message in field_messages
                ]
                if messages:
                    return " ".join(messages)
            return "; ".join(error.messages)
        return str(error)
