import os
import xml.etree.ElementTree as et

import requests

from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords
from soil_analysis.domain.valueobject.geocoder import YDF


class ReverseGeocoderService:
    @staticmethod
    def get_ydf_from_coords(coords: GoogleMapCoords) -> YDF:
        xml_str = ReverseGeocoderService._fetch_xml(coords)
        ydf = ReverseGeocoderService._xml_to_ydf(xml_str)
        return ydf

    @staticmethod
    def _fetch_xml(coords: GoogleMapCoords) -> str:
        params = {
            "lat": coords.latitude,
            "lon": coords.longitude,
            "appid": os.environ.get("YAHOO_CLIENT_ID"),
            "datum": "wgs",  # 世界測地系（デフォルト）
            "output": "xml",  # XML形式（デフォルト）
        }

        request_url = "https://map.yahooapis.jp/geoapi/V1/reverseGeoCoder"
        response = requests.get(request_url, params=params)
        print(f"{response.url=}")
        response.raise_for_status()

        return response.text

    @staticmethod
    def _xml_to_ydf(xml_str: str) -> YDF:
        """
        Converts an XML string to a YDF (Yahoo Data Format) object.

        Args:
            xml_str: A string containing the XML data.

        Returns:
            A YDF object containing the converted data.
        """
        ns = {"ns": "http://olp.yahooapis.jp/ydf/1.0"}

        tree = et.ElementTree(et.fromstring(xml_str))
        root = tree.getroot()

        result_info_element = root.find("ns:ResultInfo", ns)

        result_info = YDF.ResultInfo(
            count=int(result_info_element.find("ns:Count", ns).text),
            total=int(result_info_element.find("ns:Total", ns).text),
            start=int(result_info_element.find("ns:Start", ns).text),
            latency=float(result_info_element.find("ns:Latency", ns).text),
            status=int(result_info_element.find("ns:Status", ns).text),
            description=result_info_element.find("ns:Description", ns).text,
        )

        feature_element = root.find("ns:Feature", ns)

        country_element = feature_element.find("ns:Property/ns:Country", ns)
        country = YDF.Feature.Country(
            code=country_element.find("ns:Code", ns).text,
            name=country_element.find("ns:Name", ns).text,
        )

        geometry_element = feature_element.find("ns:Geometry", ns)
        geometry = YDF.Feature.Geometry(
            type=geometry_element.find("ns:Type", ns).text,
            coordinates=geometry_element.find("ns:Coordinates", ns).text,
        )

        address = feature_element.find("ns:Property/ns:Address", ns).text

        address_elements_elements = feature_element.findall(
            "ns:Property/ns:AddressElement", ns
        )
        address_elements = [
            YDF.Feature.AddressElement(
                name=element.find("ns:Name", ns).text,
                kana=element.find("ns:Kana", ns).text,
                level=element.find("ns:Level", ns).text,
                code=(
                    element.find("ns:Code", ns).text
                    if element.find("ns:Code", ns) is not None
                    else None
                ),
            )
            for element in address_elements_elements
        ]

        feature = YDF.Feature(
            geometry=geometry,
            country=country,
            address=address,
            address_elements=address_elements,
        )

        return YDF(result_info=result_info, feature=feature)
