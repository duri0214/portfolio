from ...models import ReadingSupportEntry
from ..valueobject.reading_support import (
    ReadingSupportDefinition,
    ReadingSupportDictionary,
)


class ReadingSupportRepository:
    """DBの読み仮名支援辞書をドメイン値へ変換するリポジトリ。"""

    def find_by_normalized_word(
        self, normalized_word: str
    ) -> ReadingSupportEntry | None:
        """正規化表記に一致する辞書エントリを返す。"""
        return ReadingSupportEntry.objects.filter(
            normalized_word=normalized_word
        ).first()

    def save_entry(self, entry: ReadingSupportEntry) -> ReadingSupportEntry:
        """辞書エントリを保存する。"""
        entry.save()
        return entry

    def get_dictionary(self) -> ReadingSupportDictionary:
        """登録済みの辞書エントリを読み仮名支援辞書として返す。"""
        entries = ReadingSupportEntry.objects.all().order_by("pk")
        return ReadingSupportDictionary(
            entries=tuple(
                ReadingSupportDefinition(
                    word=entry.word,
                    reading=entry.reading,
                    description=entry.description,
                    source_url=entry.source_url,
                )
                for entry in entries
            )
        )
