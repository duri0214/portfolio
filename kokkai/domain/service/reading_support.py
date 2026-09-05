import re
from collections.abc import Iterable

import jaconv
from janome.tokenizer import Tokenizer

from ..valueobject.reading_support import (
    READING_SUPPORT_DICTIONARY,
    ReadingSupportDictionary,
    SpeechAnnotation,
    SpeechTextSegment,
    TermDefinition,
)


class ReadingSupportService:
    """
    会議録本文へ辞書に基づく読み仮名と用語情報を付加するサービス。

    `_KANJI_LIKE_PATTERN` は、読み仮名を付ける候補を絞る簡易判定である。
    `一-龯` は個別の文字列ではなく、U+4E00（一）からU+9FAF（龯）までの
    Unicodeコードポイント範囲で、20,912コードポイントを含む。Unicode公式の
    CJK統合漢字全体にはU+9FB0以降や拡張範囲もあるため、この判定は全範囲を
    網羅しない。`々・〆・ヵ・ヶ` は範囲外から追加した読み候補文字である。

    参照:
        Unicode公式 Unihan Grid Index:
        https://www.unicode.org/charts/unihangridindex.html

    Attributes:
        tokenizer: 本文を形態素へ分割するJanomeのトークナイザー。
        dictionary: 用語定義と読み補正をまとめた読み仮名支援辞書。
        _KANJI_LIKE_PATTERN: 漢字等を含む読み仮名候補を検出する正規表現。
        _WHITESPACE_PATTERN: 表記の正規化で空白を除去する正規表現。
    """

    _KANJI_LIKE_PATTERN = re.compile(r"[一-龯々〆ヵヶ]")
    _WHITESPACE_PATTERN = re.compile(r"\s+")

    def __init__(
        self,
        tokenizer: Tokenizer | None = None,
        dictionary: ReadingSupportDictionary = READING_SUPPORT_DICTIONARY,
    ) -> None:
        self.tokenizer = tokenizer or Tokenizer()
        self.dictionary = dictionary

    def annotate(self, text: str) -> SpeechAnnotation:
        """本文を原文順のセグメントへ分け、読み仮名と登録用語を付加する。"""
        if not text:
            return SpeechAnnotation(segments=())

        segments: list[SpeechTextSegment] = []
        cursor = 0
        for start, end, term in self._find_term_spans(text):
            segments.extend(self._annotate_plain_text(text[cursor:start]))
            segments.append(SpeechTextSegment(text=text[start:end], term=term))
            cursor = end
        segments.extend(self._annotate_plain_text(text[cursor:]))
        return SpeechAnnotation(segments=tuple(self._merge_plain_segments(segments)))

    def _annotate_plain_text(self, text: str) -> list[SpeechTextSegment]:
        if not text:
            return []

        segments: list[SpeechTextSegment] = []
        cursor = 0
        for start, end, reading in self._find_reading_override_spans(text):
            segments.extend(self._tokenize(text[cursor:start]))
            segments.append(SpeechTextSegment(text=text[start:end], reading=reading))
            cursor = end
        segments.extend(self._tokenize(text[cursor:]))
        return segments

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

    def _find_term_spans(self, text: str) -> list[tuple[int, int, TermDefinition]]:
        normalized_text, positions = self._normalize_with_positions(text)
        candidates: list[tuple[int, int, TermDefinition]] = []
        for term in self.dictionary.terms:
            normalized_term = self._normalize(term.surface)
            if not normalized_term:
                continue
            search_start = 0
            while True:
                match_start = normalized_text.find(normalized_term, search_start)
                if match_start < 0:
                    break
                match_end = match_start + len(normalized_term)
                if self._has_term_boundary(normalized_text, match_start, match_end):
                    original_start = positions[match_start]
                    original_end = positions[match_end - 1] + 1
                    candidates.append((original_start, original_end, term))
                search_start = match_end

        selected: list[tuple[int, int, TermDefinition]] = []
        for candidate in sorted(
            candidates, key=lambda item: (item[0], -(item[1] - item[0]))
        ):
            if selected and candidate[0] < selected[-1][1]:
                continue
            selected.append(candidate)
        return selected

    def _find_reading_override_spans(self, text: str) -> list[tuple[int, int, str]]:
        spans = []
        for override in self.dictionary.reading_overrides:
            surface = override.surface
            reading = override.reading
            search_start = 0
            while True:
                start = text.find(surface, search_start)
                if start < 0:
                    break
                spans.append((start, start + len(surface), reading))
                search_start = start + len(surface)
        return sorted(spans, key=lambda item: item[0])

    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = jaconv.normalize(value)
        return cls._WHITESPACE_PATTERN.sub("", normalized).casefold()

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
    def _has_term_boundary(text: str, start: int, end: int) -> bool:
        """英数字の一部だけを用語として誤検出しない。"""
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
                and segment.term is None
                and not merged[-1].reading
                and merged[-1].term is None
            ):
                previous = merged[-1]
                merged[-1] = SpeechTextSegment(text=previous.text + segment.text)
            else:
                merged.append(segment)
        return merged
