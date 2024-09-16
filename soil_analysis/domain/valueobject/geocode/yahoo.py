from dataclasses import dataclass


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
        """Class to store information about a result.

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
        """class Feature:

        This class represents a feature with various attributes.

        Args:
            geometry (Feature.Geometry): The geometry of the feature.
            country (Feature.Country): The country where the feature is located.
            address_full (str): The full address of the feature.
            prefecture (Optional[Feature.Prefecture]): The prefecture of the feature, if available.
            city (Optional[Feature.City]): The city of the feature, if available.
            detail (Optional[Feature.Detail]): The detail of the feature, if available.

        Attributes:
            geometry (Feature.Geometry): The geometry of the feature.
            country (Feature.Country): The country where the feature is located.
            address_full (str): The full address of the feature.
            prefecture (Optional[Feature.Prefecture]): The prefecture of the feature, if available.
            city (Optional[Feature.City]): The city of the feature, if available.
            detail (Optional[Feature.Detail]): The detail of the feature, if available.
        """

        @dataclass
        class Geometry:
            """a geometric shape

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
            """a country

            Attributes:
                code (str): The country code.
                name (str): The name of the country.
            """

            code: str
            name: str

        @dataclass
        class AddressElement:
            """Represents an element of an address

            Attributes:
                name (str): The name of the address element.
                kana (str): The kana representation of the address element.
                level (str): The level of the address element.
                code (Optional[str]): The code of the address element, if available.
            """

            name: str
            kana: str
            level: str
            code: str = None

        @dataclass
        class Prefecture(AddressElement):
            """a prefecture"""

            def __init__(self, name: str, kana: str, code: str = None):
                super().__init__(name=name, kana=kana, level="prefecture", code=code)

        @dataclass
        class City(AddressElement):
            """a city"""

            def __init__(self, name: str, kana: str, code: str = None):
                super().__init__(name=name, kana=kana, level="city", code=code)

        @dataclass
        class Detail(AddressElement):
            """address detail"""

            def __init__(self, name: str, kana: str, code: str = None):
                super().__init__(name=name, kana=kana, level="detail", code=code)

        geometry: Geometry
        country: Country
        address_full: str
        prefecture: Prefecture
        city: City
        detail: Detail

    result_info: ResultInfo
    feature: Feature
