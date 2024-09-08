import os
import xml.etree.ElementTree as et

import requests

from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords
from soil_analysis.domain.valueobject.geocode.yahoo import YDF
from soil_analysis.models import JmaCity


class ReverseGeocoderService:
    @staticmethod
    def get_ydf_from_coords(coords: GoogleMapCoords) -> YDF:
        """
        Args:
            coords: The GoogleMapCoords
        Returns:
            An instance of the YDF obtained from the GoogleMapCoords
        """
        xml_str = ReverseGeocoderService._fetch_xml(coords)
        return ReverseGeocoderService._xml_to_ydf(xml_str)

    @staticmethod
    def get_jma_city(ydf: YDF) -> JmaCity:
        """
        Args:
            ydf: The YDF
        Returns:
            JmaCity: The JmaCity object via city name in the YDF object
        """
        return JmaCity.objects.select_related("jma_region__jma_prefecture").get(
            name=ydf.feature.city.name
        )

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

        address_full = feature_element.find("ns:Property/ns:Address", ns).text

        address_elements = feature_element.findall("ns:Property/ns:AddressElement", ns)
        first, second, *remaining = address_elements
        prefecture = YDF.Feature.Prefecture(
            name=first.find("ns:Name", ns).text,
            kana=first.find("ns:Kana", ns).text,
            code=(
                first.find("ns:Code", ns).text
                if first.find("ns:Code", ns) is not None
                else None
            ),
        )
        city = YDF.Feature.City(
            name=second.find("ns:Name", ns).text,
            kana=second.find("ns:Kana", ns).text,
            code=(
                second.find("ns:Code", ns).text
                if second.find("ns:Code", ns) is not None
                else None
            ),
        )
        detail_elements = [
            {
                "name": element.find("ns:Name", ns).text,
                "kana": element.find("ns:Kana", ns).text,
                "code": (
                    element.find("ns:Code", ns).text
                    if element.find("ns:Code", ns)
                    else None
                ),
            }
            for element in remaining
        ]
        detail = YDF.Feature.Detail(
            name="".join(
                [elem["name"] for elem in detail_elements if elem["name"] is not None]
            ),
            kana="".join(
                [elem["kana"] for elem in detail_elements if elem["kana"] is not None]
            ),
            code="".join(
                [elem["code"] for elem in detail_elements if elem["code"] is not None]
            ),
        )

        feature = YDF.Feature(
            geometry=geometry,
            country=country,
            address_full=address_full,
            prefecture=prefecture,
            city=city,
            detail=detail,
        )

        return YDF(result_info=result_info, feature=feature)
