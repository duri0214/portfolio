from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RagMetadataBase(ABC):
    """
    RAGマテリアルのメタデータを表す基底Value Object
    """

    @abstractmethod
    def to_dict(self) -> dict:
        """辞書形式に変換"""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict):
        """辞書からインスタンスを作成"""
        pass


@dataclass(frozen=True)
class GoogleMapsMetadata(RagMetadataBase):
    """
    Google Mapsレビューメタデータを表すValue Object

    Args:
        rating: レーティング（1.0-5.0）
        latitude: 緯度
        longitude: 経度
        author_name: レビュー投稿者名
        review_date: レビュー投稿日時
        location_name: 場所名
    """

    rating: float
    latitude: float
    longitude: float
    author_name: str
    review_date: datetime
    location_name: str

    def __post_init__(self):
        if not (1.0 <= self.rating <= 5.0):
            raise ValueError("rating must be between 1.0 and 5.0")
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError("latitude must be between -90.0 and 90.0")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError("longitude must be between -180.0 and 180.0")
        if not self.author_name:
            raise ValueError("author_name cannot be empty")
        if not self.location_name:
            raise ValueError("location_name cannot be empty")

    def to_dict(self) -> dict:
        return {
            "rating": self.rating,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "author_name": self.author_name,
            "review_date": self.review_date.isoformat(),
            "location_name": self.location_name,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            rating=float(data["rating"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            author_name=data["author_name"],
            review_date=datetime.fromisoformat(data["review_date"]),
            location_name=data["location_name"],
        )


@dataclass(frozen=True)
class PdfSourceMetadata(RagMetadataBase):
    """
    PDFソースメタデータを表すValue Object

    Args:
        file_path: PDFファイルのパス
    """

    file_path: str

    def __post_init__(self):
        if not self.file_path:
            raise ValueError("file_path cannot be empty")

    def to_dict(self) -> dict:
        return {"file_path": self.file_path}

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            file_path=data["file_path"],
        )
