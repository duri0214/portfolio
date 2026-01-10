"""
このファイルは試作品（プロトタイプ）です。
lib.llm に並ぶ他のライブラリとは品質や設計の意図が異なります。
"""

from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class TweetText:
    text: str


@dataclass
class TweetCollection:
    category: str  # "kawaii" or "taste"
    tweets: List[TweetText]


@dataclass
class EmbeddingVector:
    text: str
    vector: np.ndarray


@dataclass
class EmbeddingCollection:
    category: str
    embeddings: List[EmbeddingVector]


@dataclass
class SimilarityResult:
    mean: float
    median: float
    max: float
    min: float


@dataclass
class SimilarityMatrix:
    category_a: str
    category_b: str
    matrix: np.ndarray
    stats: SimilarityResult
