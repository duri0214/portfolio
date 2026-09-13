import re
from dataclasses import dataclass

import jaconv


@dataclass(frozen=True)
class ReadingSupportDefinition:
    """
    会議録本文から検出して表示する辞書項目の定義。

    Attributes:
        word: 本文中で表示する代表表記。
        reading: Janomeの結果より優先して表示する読み。
        description: 用語の短い説明。
        source_url: 説明の根拠となる公式資料のURL。空ならリンクを表示しない。
    """

    word: str
    reading: str
    description: str
    source_url: str


@dataclass(frozen=True)
class ReadingSupportDictionary:
    """
    読み補正と説明表示に使う辞書項目の集合。

    Attributes:
        entries: 本文から検出する辞書項目の集合。
    """

    entries: tuple[ReadingSupportDefinition, ...]


@dataclass(frozen=True)
class ReadingSupportImportError:
    """
    CSVの1行に対する検証エラー。

    Attributes:
        line_number: エラーが発生したCSVの行番号。
        message: 利用者へ表示する検証エラーメッセージ。
    """

    line_number: int
    message: str


@dataclass(frozen=True)
class ReadingSupportImportResult:
    """
    CSV取り込みの件数とエラーを表す結果。

    Attributes:
        created: 新規作成した辞書項目の件数。
        updated: 上書きした辞書項目の件数。
        errors: CSVの検証エラーの一覧。
    """

    created: int = 0
    updated: int = 0
    errors: tuple[ReadingSupportImportError, ...] = ()

    @property
    def is_success(self) -> bool:
        """検証エラーがなく、取り込みに成功した結果かを返す。"""
        return not self.errors


_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_word(value: str) -> str:
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
        entry: 本文に辞書項目が含まれる場合の定義。該当しない場合はNone。
    """

    text: str
    reading: str | None = None
    entry: ReadingSupportDefinition | None = None


@dataclass(frozen=True)
class SpeechAnnotation:
    """
    1件の会議録本文を学習補助表示用に分割した値。

    Attributes:
        segments: 原文の順序を保った読み仮名支援付きの本文部分。
        reading_source_url: 読みの根拠として案内するJanome公式ドキュメントのURL。
    """

    segments: tuple[SpeechTextSegment, ...]
    reading_source_url: str = "https://janome.mocobeta.dev/ja/"

    @property
    def has_support(self) -> bool:
        """読み仮名または登録用語の表示対象が含まれるかを返す。"""
        return any(segment.reading or segment.entry for segment in self.segments)
