from dataclasses import dataclass


@dataclass(frozen=True)
class WelfareFacilityVO:
    """福祉事務所のバリューオブジェクト"""

    name: str  # 名称
    postal_code: str  # 郵便番号
    address: str  # 住所
    latitude: float = None  # 緯度
    longitude: float = None  # 経度
    coordinate_system: str = None  # 座標系
    phone: str = None  # 電話
    fax: str = None  # FAX番号

    @classmethod
    def from_api_response(cls, data):
        """APIレスポンスからバリューオブジェクトを生成"""
        return cls(
            name=data.get("名称", ""),
            postal_code=data.get("郵便番号", "").strip(),
            address=data.get("住所", ""),
            latitude=data.get("緯度"),
            longitude=data.get("経度"),
            coordinate_system=data.get("座標系"),
            phone=data.get("電話"),
            fax=data.get("ＦＡＸ番号"),
        )

    def get_full_address(self):
        """完全な住所を返す"""
        return f"〒{self.postal_code} {self.address}"
