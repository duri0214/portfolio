"""
# TODO(langchain-removal):
# This module exists only for backward compatibility.
# LangChain dependency will be fully removed.
# Do NOT use this module in new code.
# Planned removal steps:
# 1. Introduce OpenAI-direct RAG implementation
# 2. Switch all callers to the new implementation via rag_core.base interfaces
# 3. Delete this module and remove langchain from requirements.txt

LangChain 隔離ゾーン: 既存コードからの参照を一時的に受け止めるための薄いラッパー/再エクスポート。
新規コードは import しないこと。
"""

from __future__ import annotations

# 再エクスポート（最小限・必要分のみ）
from langchain.schema import Document  # noqa: F401
from langchain_community.document_loaders import PyPDFLoader  # noqa: F401
from langchain_text_splitters import (  # noqa: F401
    RecursiveCharacterTextSplitter,
)

# RAG チェーン/プロンプト/ベクトルストア/モデル
from langchain.chains.qa_with_sources.retrieval import (  # noqa: F401
    RetrievalQAWithSourcesChain,
)
from langchain.prompts import ChatPromptTemplate  # noqa: F401
from langchain_chroma import Chroma  # noqa: F401
from langchain_openai import ChatOpenAI  # noqa: F401
from langchain_openai import OpenAIEmbeddings  # noqa: F401
