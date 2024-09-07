from dataclasses import dataclass
from typing import List, Optional


@dataclass
class YDF:
    """
    Class YDF

    Represents a YDF object.

    Attributes:
        result_info (ResultInfo): Information about the results of the YDF query.
        feature (Feature): Information about a particular feature returned by the YDF query.
    """

    @dataclass
    class ResultInfo:
        """
        Class to store information about a result.

        Attributes:
            count (int): The count of results.
            total (int): The total number of results.
            start (int): The starting index of the results.
            latency (float): The latency of the query.
            status (int): The status code of the query.
            description (str): The description of the query.
        """

        count: int
        total: int
        start: int
        latency: float
        status: int
        description: str

    @dataclass
    class Feature:
        """
        A class representing a feature.

        Attributes:
            geometry (Feature.Geometry): The geometry of the feature.
            country (Feature.Country): The country of the feature.
            address (str): The address of the feature.
            address_elements (List[Feature.AddressElement]): The list of address elements of the feature.
        """

        @dataclass
        class Geometry:
            """
            Represents a geometric shape.

            Args:
                type (str): The type of the geometric shape.
                coordinates (str): The coordinates of the shape.

            Attributes:
                type (str): The type of the geometric shape.
                coordinates (str): The coordinates of the shape.
            """

            type: str
            coordinates: str

        @dataclass
        class Country:
            """A class representing a country.

            Attributes:
                code (str): The country code.
                name (str): The name of the country.
            """

            code: str
            name: str

        @dataclass
        class AddressElement:
            """Represents an element of an address.

            Attributes:
                name (str): The name of the address element.
                kana (str): The kana representation of the address element.
                level (str): The level of the address element.
                code (Optional[str]): The code of the address element, if available.
            """

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
