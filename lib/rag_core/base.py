"""
RAG Core: Base interfaces

このモジュールは RAG 機能の抽象インターフェースを定義します。
LangChain 撤去後も安定した API として残すことを目的とします。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class SupportsRagQuery(Protocol):
    """RAG クエリ用の最低限のプロトコル。

    実装は dict や専用の VO を受け取っても構いませんが、まずは最小に保ちます。
    """

    def retrieve_answer(self, message: Any, /) -> Any:  # pragma: no cover
        ...


class BaseRagEngine(ABC):
    """RAG エンジンの抽象クラス。"""

    @abstractmethod
    def retrieve_answer(self, message: Any) -> Any:  # pragma: no cover
        """質問に対する回答を返します。"""
        raise NotImplementedError
