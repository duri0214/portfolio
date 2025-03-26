from dataclasses import dataclass
from typing import Optional

from soil_analysis.models import Land


@dataclass(frozen=True)
class PhotoLandAssociation:
    """写真と圃場の紐づけを表現する値オブジェクト。

    写真パスと、その写真に対応する最寄りの圃場情報を保持します。
    """

    photo_path: str
    nearest_land: Land
    distance: Optional[float] = None

    def __str__(self) -> str:
        """人間が読みやすい形式で紐づけ情報を返します。"""
        distance_info = (
            f", 距離: {self.distance:.1f}m" if self.distance is not None else ""
        )
        return (
            f"写真: {self.photo_path} → 圃場: {self.nearest_land.name}{distance_info}"
        )
