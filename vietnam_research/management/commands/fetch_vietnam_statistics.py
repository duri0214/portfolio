import xml.etree.ElementTree as et
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from django.core.management.base import BaseCommand


@dataclass
class Obs:
    element: str
    period_str: str
    value: float
    period: datetime = field(init=False)

    def __post_init__(self):
        self.period = self.get_datetime()

    def get_datetime(self) -> datetime:
        year, month = map(int, self.period_str.split("-"))
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        last_day_of_month = next_month - timedelta(days=1)
        return last_day_of_month


# XMLデータのパース
def fetch_data(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def parse_xml(
    element_name: str, xml_data: str, data_domain: str, ref_area: str, indicator: str
):
    root = et.fromstring(xml_data)
    observations = []
    for series in root.findall(".//Series"):
        if (
            series.get("DATA_DOMAIN") == data_domain
            and series.get("REF_AREA") == ref_area
            and series.get("INDICATOR") == indicator
        ):
            for obs in series.findall("Obs"):
                period_str = obs.get("TIME_PERIOD")
                value = float(obs.get("OBS_VALUE"))
                observation = Obs(
                    element=element_name, period_str=period_str, value=value
                )
                observations.append(observation)
    return observations


class Command(BaseCommand):
    help = "Fetch Vietnam Statistics data"

    def handle(self, *args, **options):
        """
        https://www.gso.gov.vn/
        Args:
            *args:
            **options:
        """
        # VietnamStatistics.objects.all().delete()

        # data1: 鉱工業生産指数
        url = "https://nsdp.gso.gov.vn/GSO-chung/SDMXFiles/GSO/IIPVNM.xml"
        xml_data = fetch_data(url)
        element_name = "industrial production index"
        data_domain = "IND"
        ref_area = "VN"
        indicator = "AIP_ISIC4_IX"
        industrial_production_index = parse_xml(
            element_name, xml_data, data_domain, ref_area, indicator
        )

        for obs in industrial_production_index:
            print(obs)
            # Obs.objects.create(
            #     period_str=obs.period_str, value=obs.value, period=obs.period
            # )

        self.stdout.write(
            self.style.SUCCESS("Successfully fetched and stored Vietnam IIP data.")
        )

        # data2: 消費者物価指数
        url = "https://nsdp.gso.gov.vn/GSO-chung/SDMXFiles/GSO/CPIVNM.xml"
        xml_data = fetch_data(url)
        element_name = "consumer price index"
        data_domain = "CPI"
        ref_area = "VN"
        indicator = "PCPI_IX"
        consumer_price_index = parse_xml(
            element_name, xml_data, data_domain, ref_area, indicator
        )

        for obs in consumer_price_index:
            print(obs)

        self.stdout.write(
            self.style.SUCCESS("Successfully fetched and stored Vietnam CPI data.")
        )

        url = "https://vietnamtourism.gov.vn/en/statistic/international?year=2024&period=t5"
