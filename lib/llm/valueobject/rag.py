import os
from abc import ABC, abstractmethod

# TODO(langchain-removal):
# LangChain 直接依存の隔離。新規コードは使用禁止。
# 代わりに OpenAI-direct 実装へ段階的に移行予定。
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


class Dataloader(ABC):
    pages: list[Document] = []

    @property
    @abstractmethod
    def data(self) -> list[Document]:
        pass

    @abstractmethod
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    @abstractmethod
    def _load(self):
        """
        See Also: https://python.langchain.com/docs/how_to/document_loader_pdf/
        """
        pass

    @abstractmethod
    def _split(self):
        """
        各ページに出典（ページ数）をつけます
        """
        pass

    def _shredder(self, source: str, attr: str) -> tuple:
        """
        日本語PDFでトークンを多く消費するような場合、ページ単位ではAPIが処理できないので
        さらに千切りにする
        """
        all_splits = self.text_splitter.split_documents(self.pages)
        all_text, all_metadata = [], []
        for text_fragment in all_splits:
            all_text.extend(text_fragment)
            all_metadata.extend({"source": source, "attr": attr})

        return all_text, all_metadata


class PdfDataloader(Dataloader):
    @property
    def data(self) -> list[Document]:
        return self.pages

    def __init__(self, file_path: str):
        super().__init__()
        self._file_path = file_path
        self._load()
        self._split()

    def _load(self):
        # TODO: 非同期化したいね https://python.langchain.com/docs/how_to/document_loader_pdf/#simple-and-fast-text-extraction
        self.pages = PyPDFLoader(self._file_path).load()

    def _split(self):
        filename = os.path.basename(self._file_path)
        for i, doc in enumerate(self.pages):
            doc.page_content = doc.page_content.replace("\n", " ")
            doc.metadata = {"source": f"{filename} {i + 1}ページ"}


class RetrievalQAWithSourcesChainAnswer:
    def __init__(
        self, question: str, answer: str, sources: str, source_documents: list[Document]
    ):
        self.question = question
        self.answer = answer
        self.sources = sources
        self.source_documents = source_documents
