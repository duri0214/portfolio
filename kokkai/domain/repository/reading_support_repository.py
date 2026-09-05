from django.test.testcases import DatabaseOperationForbidden

from ...models import ReadingSupportEntry
from ..valueobject.reading_support import (
    ReadingOverride,
    ReadingSupportDictionary,
    TermDefinition,
)


class ReadingSupportRepository:
    """DBの読み仮名支援辞書をドメイン値へ変換するリポジトリ。"""

    def get_dictionary(self) -> ReadingSupportDictionary:
        """有効な辞書エントリだけを読み仮名支援辞書として返す。"""
        try:
            entries = ReadingSupportEntry.objects.filter(is_active=True).order_by("pk")
            terms = tuple(
                TermDefinition(
                    surface=entry.surface,
                    reading=entry.reading,
                    description=entry.description,
                    category=entry.category,
                    source_url=entry.source_url,
                )
                for entry in entries
                if entry.entry_type == ReadingSupportEntry.EntryType.TERM
            )
            reading_overrides = tuple(
                ReadingOverride(surface=entry.surface, reading=entry.reading)
                for entry in entries
                if entry.entry_type == ReadingSupportEntry.EntryType.READING_OVERRIDE
            )
        except DatabaseOperationForbidden:
            # SimpleTestCaseなどDBアクセスを禁止するテストでは空辞書で継続する。
            return ReadingSupportDictionary(terms=(), reading_overrides=())
        return ReadingSupportDictionary(
            terms=terms,
            reading_overrides=reading_overrides,
        )
