from dataclasses import dataclass
from typing import List, Optional


@dataclass
class YDF:
    @dataclass
    class ResultInfo:
        count: int
        total: int
        start: int
        latency: float
        status: int
        description: str

    @dataclass
    class Feature:
        @dataclass
        class Geometry:
            type: str
            coordinates: str

        @dataclass
        class Country:
            code: str
            name: str

        @dataclass
        class AddressElement:
            name: str
            kana: str
            level: str
            code: Optional[str]

        geometry: Geometry
        country: Country
        address: str
        address_elements: List[AddressElement]

    result_info: ResultInfo
    feature: Feature
