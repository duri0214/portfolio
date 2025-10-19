from dataclasses import dataclass
from typing import Protocol

from lib.pptx_generator.valueobject import MarkdownSection, Table


class ShapeOp(Protocol):
    """特定の図形名に対して適用する操作を表すプロトコル。

    注意: このモジュールは「何を適用するか」の記述のみに留め、
    実際の PPTX（XML）の操作は I/O と名前空間を一元管理するために
    PptxToxicService 側に委ねます。
    """

    name_key: str


@dataclass(frozen=True)
class TextOp:
    name_key: str
    text: str


@dataclass(frozen=True)
class TableOp:
    name_key: str
    table: Table


class ShapeOperationFactory:
    """MarkdownSection から図形操作のリストを生成するファクトリ。

    マッピングで使用するキーは PptxToxicService と互換である必要があります:
    - "title", "paragraphs", "bullet_list", "table"。
    """

    @staticmethod
    def build(source: MarkdownSection) -> list[ShapeOp]:
        """MarkdownSection から ShapeOp の配列を構築する。

        方針:
        - 箇条書き（bullet_list）のレンダリングはサービス層（PptxToxicService）の
          BulletStyle に委譲することで単一責任を保つ。
          そのため本ファクトリではテキストを事前整形せず、空文字をセットした
          TextOp("bullet_list", "") を渡す。サービス側が元の MarkdownSection から
          適切なスタイルで再レンダリングすることを想定する。
        - 段落は "\n\n" 区切りで結合して渡す。
        - テーブルは TableOp としてそのまま渡す。
        """
        operations: list[ShapeOp] = []
        if source.title is not None:
            operations.append(TextOp("title", source.title))
        if source.paragraphs:
            operations.append(TextOp("paragraphs", "\n\n".join(source.paragraphs)))
        if source.bullet_list and source.bullet_list.items:
            operations.append(TextOp("bullet_list", ""))
        if source.table and source.table.records:
            operations.append(TableOp("table", source.table))
        return operations
