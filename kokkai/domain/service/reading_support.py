import re
from collections.abc import Iterable

from janome.tokenizer import Tokenizer

from ..repository.reading_support_repository import ReadingSupportRepository
from ..valueobject.reading_support import (
    ReadingSupportDefinition,
    ReadingSupportDictionary,
    SpeechAnnotation,
    SpeechTextSegment,
    normalize_word,
)


class ReadingSupportService:
    """
    会議録本文へ辞書に基づく読み仮名と説明情報を付加するサービス。

    Attributes:
        tokenizer: 本文を形態素へ分割するJanomeのトークナイザー。
        dictionary: 読みと説明をまとめた読み仮名支援辞書。
        _KANJI_LIKE_PATTERN: 漢字等を含む読み仮名候補を検出する正規表現。
    """

    _KANJI_LIKE_PATTERN = re.compile(r"[一-龯々〆ヵヶ]")

    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        dictionary: ReadingSupportDictionary | None = None,
    ) -> None:
        self.tokenizer = tokenizer or Tokenizer()
        self.dictionary = (
            dictionary
            if dictionary is not None
            else ReadingSupportRepository().get_dictionary()
        )

    def annotate(self, text: str) -> SpeechAnnotation:
        """本文を原文順のセグメントへ分け、読み仮名と登録用語を付加する。"""
        if not text:
            return SpeechAnnotation(segments=())

        segments: list[SpeechTextSegment] = []
        cursor = 0
        for start, end, entry in self._find_entry_spans(text):
            segments.extend(self._tokenize(text[cursor:start]))
            segments.append(
                SpeechTextSegment(
                    text=text[start:end], reading=entry.reading, entry=entry
                )
            )
            cursor = end
        segments.extend(self._tokenize(text[cursor:]))
        return SpeechAnnotation(segments=tuple(self._merge_plain_segments(segments)))

    def _tokenize(self, text: str) -> list[SpeechTextSegment]:
        segments = []
        for token in self.tokenizer.tokenize(text):
            reading = self._reading_for_token(token)
            segments.append(SpeechTextSegment(text=token.surface, reading=reading))
        return segments

    @classmethod
    def _reading_for_token(cls, token) -> str | None:
        """Janomeの結果から、誤読を断定しにくい語だけの読みを返す。"""
        if not cls._KANJI_LIKE_PATTERN.search(token.surface):
            return None
        if token.reading in (None, "*", token.surface):
            return None
        part_of_speech = token.part_of_speech.split(",")
        if len(part_of_speech) > 1 and part_of_speech[:2] == ["名詞", "固有名詞"]:
            return None
        return token.reading

    def _find_entry_spans(
        self, text: str
    ) -> list[tuple[int, int, ReadingSupportDefinition]]:
        normalized_text, positions = self._normalize_with_positions(text)
        candidates: list[tuple[int, int, ReadingSupportDefinition]] = []
        for entry in self.dictionary.entries:
            normalized_entry = self._normalize(entry.word)
            if not normalized_entry:
                continue
            search_start = 0
            while True:
                match_start = normalized_text.find(normalized_entry, search_start)
                if match_start < 0:
                    break
                match_end = match_start + len(normalized_entry)
                if self._has_entry_boundary(normalized_text, match_start, match_end):
                    original_start = positions[match_start]
                    original_end = positions[match_end - 1] + 1
                    candidates.append((original_start, original_end, entry))
                search_start = match_end

        selected: list[tuple[int, int, ReadingSupportDefinition]] = []
        for candidate in sorted(
            candidates, key=lambda item: (item[0], -(item[1] - item[0]))
        ):
            if selected and candidate[0] < selected[-1][1]:
                continue
            selected.append(candidate)
        return selected

    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_word(value)

    @classmethod
    def _normalize_with_positions(cls, value: str) -> tuple[str, list[int]]:
        normalized_chars: list[str] = []
        positions: list[int] = []
        for index, character in enumerate(value):
            normalized_character = cls._normalize(character)
            for normalized_part in normalized_character:
                normalized_chars.append(normalized_part)
                positions.append(index)
        return "".join(normalized_chars), positions

    @staticmethod
    def _has_entry_boundary(text: str, start: int, end: int) -> bool:
        """英数字の一部だけを辞書項目として誤検出しない。"""
        return not (
            (start > 0 and text[start - 1].isascii() and text[start - 1].isalnum())
            or (end < len(text) and text[end].isascii() and text[end].isalnum())
        )

    @staticmethod
    def _merge_plain_segments(
        segments: Iterable[SpeechTextSegment],
    ) -> list[SpeechTextSegment]:
        merged: list[SpeechTextSegment] = []
        for segment in segments:
            if (
                merged
                and not segment.reading
                and segment.entry is None
                and not merged[-1].reading
                and merged[-1].entry is None
            ):
                previous = merged[-1]
                merged[-1] = SpeechTextSegment(text=previous.text + segment.text)
            else:
                merged.append(segment)
        return merged
