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
        operations: list[ShapeOp] = []
        if source.title is not None:
            operations.append(TextOp("title", source.title))
        if source.paragraphs:
            operations.append(TextOp("paragraphs", "\n\n".join(source.paragraphs)))
        if source.bullet_list and source.bullet_list.items:
            # Defer bullet rendering to service-side BulletStyle to keep a single responsibility
            # Here we join with \n so service can decide exact styling; but to preserve behavior, we pass items list text rendering from service.
            # We will pass items via placeholder; however, ShapeOp requires text. Keep empty; service will re-render from the MarkdownSection if necessary.
            # To preserve the current exact output, we won't pre-render here; instead, the service will render from source when it sees this op.
            # We still need a text; put a sentinel that service ignores. Leaving an empty string is fine.
            operations.append(TextOp("bullet_list", ""))
        if source.table and source.table.records:
            operations.append(TableOp("table", source.table))
        return operations
