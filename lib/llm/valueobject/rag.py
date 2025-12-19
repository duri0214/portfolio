import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pypdf


@dataclass
class Document:
    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Dataloader(ABC):
    pages: list[Document]

    @property
    @abstractmethod
    def data(self) -> list[Document]:
        pass

    @abstractmethod
    def __init__(self):
        self.pages = []

    @abstractmethod
    def _load(self):
        pass

    @abstractmethod
    def _split(self):
        """
        各ページに出典（ページ数）をつけます
        """
        pass


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
        reader = pypdf.PdfReader(self._file_path)
        self.pages = [
            Document(page_content=page.extract_text(), metadata={})
            for page in reader.pages
        ]

    def _split(self):
        filename = os.path.basename(self._file_path)
        for i, doc in enumerate(self.pages):
            doc.page_content = doc.page_content.replace("\n", " ")
            doc.metadata = {"source": f"{filename} {i + 1}ページ"}
