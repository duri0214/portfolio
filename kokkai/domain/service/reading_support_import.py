from __future__ import annotations

import csv
import io
from typing import TextIO

from django.core.exceptions import ValidationError
from django.db import transaction

from ...models import ReadingSupportEntry
from ..repository.reading_support_repository import ReadingSupportRepository
from ..valueobject.reading_support import (
    ReadingSupportImportError,
    ReadingSupportImportResult,
    normalize_word,
)


class ReadingSupportCsvImporter:
    """読み仮名支援辞書CSVを検証して辞書へ取り込む。"""

    REQUIRED_COLUMNS = (
        "word",
        "reading",
        "description",
        "source_url",
    )

    def __init__(self, repository: ReadingSupportRepository | None = None) -> None:
        self.repository = repository or ReadingSupportRepository()

    def import_csv(
        self,
        source: bytes | str | TextIO,
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
        seen_words: set[str] = set()

        for row in reader:
            line_number = reader.line_num
            if self._is_empty_row(row):
                continue
            try:
                values = self._row_values(row)
                entry = self._build_entry(values)
                normalized_word = entry.normalized_word
                if normalized_word in seen_words:
                    raise ValueError("同じCSV内に同じ単語が複数あります。")
                seen_words.add(normalized_word)

                existing = self.repository.find_by_normalized_word(normalized_word)
                if existing is not None:
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
                self.repository.save_entry(entry)
                if is_new:
                    created += 1
                else:
                    updated += 1
        return ReadingSupportImportResult(
            created=created,
            updated=updated,
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
        word = values.get("word", "")
        reading = values.get("reading", "")
        description = values.get("description", "")
        source_url = values.get("source_url", "")

        return ReadingSupportEntry(
            word=word,
            normalized_word=normalize_word(word),
            reading=reading,
            description=description,
            source_url=source_url,
        )

    @staticmethod
    def _copy_values(source: ReadingSupportEntry, target: ReadingSupportEntry) -> None:
        target.word = source.word
        target.normalized_word = source.normalized_word
        target.reading = source.reading
        target.description = source.description
        target.source_url = source.source_url

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
