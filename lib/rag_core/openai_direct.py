"""
# TODO(langchain-removal):
# Replace LangChain-based logic with OpenAI-direct implementation.
# このモジュールは LangChain 依存を排除した RAG 実装を提供します。
# まずはメモリ内の簡易ベクトルストアで実装し、必要に応じて Chroma 永続化へ拡張します。

Planned steps:
1. OpenAI SDK での埋め込み生成とメモリ内ベクトルストア（本ファイル）。
2. 必要になったら Chroma 等への永続化を追加（TODO を各所に明記）。
3. 既存呼び出しを `rag_core.base.BaseRagEngine` 経由で切替。
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from openai import OpenAI
from openai.types.responses import EasyInputMessageParam

from .base import BaseRagEngine


class OpenAIDirectRag(BaseRagEngine):
    """OpenAI SDK 直接利用のシンプルな RAG 実装。

    - 埋め込み: OpenAI Embeddings API（デフォルト: text-embedding-3-small）
    - ベクトルストア: メモリ内（コサイン類似度）。
      TODO(persistence): 需要が出たら Chroma 等に永続化する。
    - 生成: OpenAI Chat Completions（`model` は呼び出し元設定を流用）。
    """

    MAX_CONTEXT_CHARS = 6000

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        documents: Sequence[Any] | None = None,
        n_results: int = 3,
        embedding_model: str = "text-embedding-3-small",
        system_template: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.n_results = n_results
        self.embedding_model = embedding_model
        self._client = OpenAI(api_key=self.api_key)

        # ドキュメントは LangChain の Document 互換（page_content, metadata）であることを想定。
        self._docs: list[Any] = list(documents or [])
        self._embeddings: list[list[float]] = []

        # 既存のプロンプト文面を流用
        self.system_template = (
            system_template
            or """
            以下の資料の注意点を念頭に置いて回答してください
            ・ユーザの質問に対して、できる限り根拠を示してください
            ・箇条書きで簡潔に回答してください。
            ---下記は資料の内容です---
            {summaries}

            Answer in Japanese:
            """
        ).strip()

        if self._docs:
            self._ensure_corpus_indexed()

    # --- public API ---
    def retrieve_answer(self, message: Any) -> dict:
        """質問に対する回答を返す。

        Args:
            message: 質問文字列、または `content` 属性を持つ VO（例: Message）。

        Returns:
            dict: {"answer": str, "sources": str, "source_documents": list, "warning": str|None}
        """
        question = _extract_text(message)
        if not question:
            raise ValueError("Message content cannot be empty for RAG query")

        if not self._docs:
            # 空のコーパスに対する問い合わせ
            return {
                "answer": "知識ベースが空です。ドキュメントを登録してから再度お試しください。",
                "sources": "",
                "source_documents": [],
                "warning": None,
            }

        if not self._embeddings:
            self._ensure_corpus_indexed()

        # 質問をベクトル化
        q_vec = self._embed_texts([question])[0]

        # Top-k 類似ドキュメントを取得
        idxes = _top_k_by_cosine(self._embeddings, q_vec, k=self.n_results)
        selected = [self._docs[i] for i in idxes]

        summaries = _join_summaries(documents=selected)
        warning = None
        # 軽量な「長さアラート」: 文字数ベース。必要ならトークン化へ改良可。
        if len(summaries) > self.MAX_CONTEXT_CHARS:
            warning = f"summaries length {len(summaries)} exceeds {self.MAX_CONTEXT_CHARS} chars; trimmed."
            summaries = summaries[: self.MAX_CONTEXT_CHARS]

        # プロンプト構築（system + user）
        system_text = self.system_template.format(summaries=summaries)

        # New SDK 推奨の Responses API を使用
        # input には許可された型（Responses API の EasyInputMessageParam）で渡す
        system_msg: EasyInputMessageParam = {"role": "system", "content": system_text}
        user_msg: EasyInputMessageParam = {"role": "user", "content": question}

        response = self._client.responses.create(
            model=self.model,
            input=[system_msg, user_msg],
        )

        # output_text があればそれを優先
        answer = getattr(response, "output_text", None) or ""
        if not answer:
            # 後方互換の保険: choices 等にメッセージがあれば拾う
            try:
                # 一部実装では `response.output[0].content[0].text` 等の構造になる
                # 最低限の防御的パース（失敗しても空文字のまま）
                output = getattr(response, "output", None)
                if output and isinstance(output, list):
                    first = output[0]
                    content = getattr(first, "content", None)
                    if content and isinstance(content, list):
                        text = getattr(content[0], "text", None)
                        value = getattr(text, "value", None)
                        if isinstance(value, str):
                            answer = value
            except (AttributeError, TypeError, IndexError):
                # 期待しないレスポンス構造だった場合のみ捕捉し、警告として返す
                warning = (warning + " | " if warning else "") + "fallback_parse_error"

        # sources を人間可読にまとめる
        sources_list = []
        for d in selected:
            meta = getattr(d, "metadata", None) or {}
            src = meta.get("source") or meta.get("file") or str(meta)
            sources_list.append(str(src))
        sources = "\n".join(dict.fromkeys(sources_list))  # 重複排除を維持したまま

        return {
            "answer": answer,
            "sources": sources,
            "source_documents": selected,
            "warning": warning,
        }

    # --- corpus management ---
    def upsert_documents(self, documents: Iterable[Any]) -> None:
        """コーパスにドキュメントを追加・更新し、必要なら再ベクトル化。"""
        self._docs.extend(list(documents))
        self._ensure_corpus_indexed(recompute=True)

    # --- internals ---
    def _ensure_corpus_indexed(self, *, recompute: bool = False) -> None:
        if self._embeddings and not recompute:
            return
        texts = [getattr(d, "page_content", str(d)) for d in self._docs]
        self._embeddings = self._embed_texts(texts)

    def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """OpenAI Embeddings API でベクトル化。"""
        if not texts:
            return []
        resp = self._client.embeddings.create(
            model=self.embedding_model, input=list(texts)
        )
        return [d.embedding for d in resp.data]


# --- helpers ---
def _extract_text(message: Any) -> str:
    if message is None:
        return ""
    if isinstance(message, str):
        return message
    # Message VO 想定（.content）
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else ""


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return (_dot(a, a)) ** 0.5


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na = _norm(a)
    nb = _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return _dot(a, b) / (na * nb)


def _top_k_by_cosine(
    matrix: Sequence[Sequence[float]], vec: Sequence[float], k: int
) -> list[int]:
    scored = [(i, _cosine(row, vec)) for i, row in enumerate(matrix)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [i for i, _ in scored[: max(k, 0)]]


def _join_summaries(documents: Sequence[Any]) -> str:
    parts: list[str] = []
    for d in documents:
        text = getattr(d, "page_content", None)
        meta = getattr(d, "metadata", None) or {}
        source = meta.get("source") or ""
        if text:
            parts.append(f"[source: {source}]\n{text}")
    return "\n\n".join(parts)
