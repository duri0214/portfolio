import re
from dataclasses import dataclass

import jaconv


@dataclass(frozen=True)
class TermDefinition:
    """
    会議録本文から検出して表示する登録用語の定義。

    Attributes:
        surface: 本文中で表示する代表表記。
        reading: 学習用に表示する用語の読み。
        description: 用語の短い説明。
        category: 用語の分類。
        source_url: 説明の根拠となる公式資料のURL。
    """

    surface: str
    reading: str
    description: str
    category: str
    source_url: str


@dataclass(frozen=True)
class ReadingOverride:
    """
    Janomeの読みを上書きする本文表記と読みの組み合わせ。

    Attributes:
        surface: 本文中で補正対象にする表記。
        reading: 表示する読み。
    """

    surface: str
    reading: str


@dataclass(frozen=True)
class ReadingSupportDictionary:
    """
    読み補正と用語解説をまとめて扱う、読み仮名支援用の辞書。

    Attributes:
        terms: 本文から検出して説明を表示する用語定義の集合。
        reading_overrides: Janomeの読みを上書きする表記と読みの集合。
    """

    terms: tuple[TermDefinition, ...]
    reading_overrides: tuple[ReadingOverride, ...]


_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_surface(value: str) -> str:
    """表記の全角・半角、大小文字、空白を検出用に正規化する。"""
    normalized = jaconv.normalize(value or "")
    return _WHITESPACE_PATTERN.sub("", normalized).casefold()


@dataclass(frozen=True)
class SpeechTextSegment:
    """
    会議録本文を読み仮名または用語情報付きで表示するための一部分。

    Attributes:
        text: 本文に現れた原文。
        reading: Janomeまたは登録済み補正による読み。表示不要ならNone。
        term: 本文に登録用語が含まれる場合の定義。該当しない場合はNone。
    """

    text: str
    reading: str | None = None
    term: TermDefinition | None = None


@dataclass(frozen=True)
class SpeechAnnotation:
    """
    1件の会議録本文を学習補助表示用に分割した値。

    Attributes:
        segments: 原文の順序を保った読み仮名・用語付きの本文部分。
        reading_source_url: 読みの根拠として案内するJanome公式ドキュメントのURL。
    """

    segments: tuple[SpeechTextSegment, ...]
    reading_source_url: str = "https://janome.mocobeta.dev/ja/"

    @property
    def has_support(self) -> bool:
        """読み仮名または登録用語の表示対象が含まれるかを返す。"""
        return any(segment.reading or segment.term for segment in self.segments)
