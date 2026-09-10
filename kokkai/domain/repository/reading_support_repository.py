from ...models import ReadingSupportEntry
from ..valueobject.reading_support import (
    ReadingOverride,
    ReadingSupportDictionary,
    TermDefinition,
)


class ReadingSupportRepository:
    """DBの読み仮名支援辞書をドメイン値へ変換するリポジトリ。"""

    def find_by_normalized_surface(
        self, normalized_surface: str
    ) -> ReadingSupportEntry | None:
        """正規化表記に一致する辞書エントリを返す。"""
        return ReadingSupportEntry.objects.filter(
            normalized_surface=normalized_surface
        ).first()

    def save_entry(self, entry: ReadingSupportEntry) -> ReadingSupportEntry:
        """辞書エントリを保存する。"""
        entry.save()
        return entry

    def get_dictionary(self) -> ReadingSupportDictionary:
        """登録済みの辞書エントリを読み仮名支援辞書として返す。"""
        entries = ReadingSupportEntry.objects.all().order_by("pk")
        terms = tuple(
            TermDefinition(
                surface=entry.surface,
                reading=entry.reading,
                description=entry.description,
                source_url=entry.source_url,
            )
            for entry in entries
            if entry.is_term
        )
        reading_overrides = tuple(
            ReadingOverride(surface=entry.surface, reading=entry.reading)
            for entry in entries
            if not entry.is_term
        )
        return ReadingSupportDictionary(
            terms=terms,
            reading_overrides=reading_overrides,
        )
