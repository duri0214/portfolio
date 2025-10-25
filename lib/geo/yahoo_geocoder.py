import os
import xml.etree.ElementTree as et

import requests

from lib.geo.valueobject.coord import GoogleMapsCoord
from lib.geo.valueobject.yahoo_geocoder import YDF


def _parse_xml_and_result_info(xml_str: str) -> tuple:
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
    return root, ns, result_info


class ReverseGeocoderService:
    @staticmethod
    def get_ydf_from_coord(coord: GoogleMapsCoord) -> YDF:
        """
        Args:
            coord: The GoogleMapsCoord
        Returns:
            An instance of the YDF obtained from the GoogleMapsCoord
        """
        xml_str = ReverseGeocoderService._fetch_xml(coord)
        return ReverseGeocoderService._xml_to_ydf(xml_str)

    @staticmethod
    def _fetch_xml(coord: GoogleMapsCoord) -> str:
        params = {
            "lat": coord.latitude,
            "lon": coord.longitude,
            "appid": os.environ.get("YAHOO_DEV_API_KEY"),
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
        root, ns, result_info = _parse_xml_and_result_info(xml_str)

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


class ForwardGeocoderService:
    @staticmethod
    def get_ydf_from_address(address: str) -> YDF:
        """
        住所文字列から詳細なYDF情報を取得する
        """
        xml_str = ForwardGeocoderService._fetch_xml(address)
        return ForwardGeocoderService._xml_to_ydf(xml_str)

    @staticmethod
    def get_coord_from_address(address: str) -> GoogleMapsCoord:
        """
        住所文字列から緯度経度を取得する
        """
        ydf = ForwardGeocoderService.get_ydf_from_address(address)
        # YahooのCoordinatesは "lon,lat" の順序
        lon_str, lat_str = ydf.feature.geometry.coordinates.split(",")
        return GoogleMapsCoord(latitude=float(lat_str), longitude=float(lon_str))

    @staticmethod
    def _fetch_xml(address: str) -> str:
        params = {
            "query": address,
            "results": 10,
            "datum": "wgs",
            "output": "xml",
            "appid": os.environ.get("YAHOO_DEV_API_KEY"),
        }
        request_url = "https://map.yahooapis.jp/geocode/V1/geoCoder"
        response = requests.get(request_url, params=params)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _xml_to_ydf(xml_str: str) -> YDF:
        root, ns, result_info = _parse_xml_and_result_info(xml_str)

        if result_info.total == 0:
            raise ValueError("No results found")

        # YahooのForwardは複数Featureが返る可能性あり。最初のFeatureのみ使用。
        feature_element = root.find("ns:Feature", ns)

        # Name (任意)
        name_el = feature_element.find("ns:Name", ns)
        feature_name = name_el.text if name_el is not None else None

        # Country (任意: ない場合もある)
        country_element = feature_element.find("ns:Property/ns:Country", ns)
        if country_element is not None:
            country = YDF.Feature.Country(
                code=(country_element.find("ns:Code", ns).text
                      if country_element.find("ns:Code", ns) is not None else ""),
                name=(country_element.find("ns:Name", ns).text
                      if country_element.find("ns:Name", ns) is not None else ""),
            )
        else:
            # フォールバック: 国情報がない場合でも空で生成
            country = YDF.Feature.Country(code="", name="")

        # Geometry (Coordinates は必須想定、BoundingBoxは任意)
        geometry_element = feature_element.find("ns:Geometry", ns)
        coordinates = geometry_element.find("ns:Coordinates", ns).text
        geom_type_el = geometry_element.find("ns:Type", ns)
        geom_type = geom_type_el.text if geom_type_el is not None else "point"

        # Optional BoundingBox
        bb_el = geometry_element.find("ns:BoundingBox", ns)
        bounding_box = None
        if bb_el is not None:
            sw = bb_el.find("ns:SouthWest", ns)
            ne = bb_el.find("ns:NorthEast", ns)
            if sw is not None and ne is not None:
                bounding_box = YDF.Feature.Geometry.BoundingBox(
                    south_west=sw.text, north_east=ne.text
                )
        geometry = YDF.Feature.Geometry(type=geom_type, coordinates=coordinates, bounding_box=bounding_box)

        # Address (任意)
        address_full = None
        addr_el = feature_element.find("ns:Property/ns:Address", ns)
        if addr_el is not None:
            address_full = addr_el.text

        # AddressElement 群（任意）
        prefecture = city = detail = None
        address_elements = feature_element.findall("ns:Property/ns:AddressElement", ns)
        if address_elements and len(address_elements) >= 1:
            first = address_elements[0]
            prefecture = YDF.Feature.Prefecture(
                name=(first.find("ns:Name", ns).text if first.find("ns:Name", ns) is not None else ""),
                kana=(first.find("ns:Kana", ns).text if first.find("ns:Kana", ns) is not None else ""),
                code=(first.find("ns:Code", ns).text if first.find("ns:Code", ns) is not None else None),
            )
        if address_elements and len(address_elements) >= 2:
            second = address_elements[1]
            city = YDF.Feature.City(
                name=(second.find("ns:Name", ns).text if second.find("ns:Name", ns) is not None else ""),
                kana=(second.find("ns:Kana", ns).text if second.find("ns:Kana", ns) is not None else ""),
                code=(second.find("ns:Code", ns).text if second.find("ns:Code", ns) is not None else None),
            )
        if address_elements and len(address_elements) > 2:
            remaining = address_elements[2:]
            detail_name = "".join([
                (el.find("ns:Name", ns).text if el.find("ns:Name", ns) is not None else "")
                for el in remaining
            ])
            detail_kana = "".join([
                (el.find("ns:Kana", ns).text if el.find("ns:Kana", ns) is not None else "")
                for el in remaining
            ])
            # codeは複合の際は連結（存在するもののみ）
            codes = [el.find("ns:Code", ns).text for el in remaining if el.find("ns:Code", ns) is not None]
            detail_code = "".join(codes) if codes else None
            detail = YDF.Feature.Detail(name=detail_name, kana=detail_kana, code=detail_code)

        feature = YDF.Feature(
            geometry=geometry,
            country=country,
            address_full=address_full,
            name=feature_name,
            prefecture=prefecture,
            city=city,
            detail=detail,
        )

        return YDF(result_info=result_info, feature=feature)
