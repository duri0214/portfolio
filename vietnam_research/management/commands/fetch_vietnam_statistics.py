import xml.etree.ElementTree as et
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from django.core.management.base import BaseCommand

from vietnam_research.models import VietnamStatistics


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

    def handle(self, **options):
        """
        このコマンドは、ベトナムの鉱工業生産指数と消費者物価指数のデータを取得、保存します。
        これらのデータはベトナム統計局のウェブサイト `https://www.gso.gov.vn/` から提供されています。

        handleメソッドは以下のタスクを実行します：

        1. VietnamStatisticsモデルのすべてのレコードを削除。
        2. 各URLから以下のデータを取得：
            - "https://nsdp.gso.gov.vn/GSO-chung/SDMXFiles/GSO/IIPVNM.xml"（工業生産指数）
            - "https://nsdp.gso.gov.vn/GSO-chung/SDMXFiles/GSO/CPIVNM.xml"（消費者物価指数）
        3. 取得データを解析し、VietnamStatisticsモデルに新たなレコードを作成。
        4. データの取得と保存が成功した場合、成功メッセージを表示。

        鉱工業生産指数は、一定期間内の鉱業および製造業の生産量を測る指標。
        この指数が増加すると、製造業の生産量が増加し、その結果、物資の流通や貿易が盛んになる可能性があります。
        ベトナム統計局のウェブサイトの「ベトナム国概要データページ」の鉱工業生産指数 - SDMXデータ をクリック

        一方、消費者物価指数は、一般的な物価水準の変動を測定。インフレまたはデフレを示す可能性があり、
        これらの状況はそれぞれ、物価上昇または下落を意味します。
        ベトナム統計局のウェブサイトの「ベトナム国概要データページ」の消費者物価指数 - SDMXデータ をクリック

        これらの指数を分析し、ベトナム経済のパフォーマンスとトレンドを把握します。
        """
        VietnamStatistics.objects.all().delete()

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

        entities = [
            VietnamStatistics(element=obs.element, period=obs.period, value=obs.value)
            for obs in industrial_production_index
        ]
        VietnamStatistics.objects.bulk_create(entities)

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

        entities = [
            VietnamStatistics(element=obs.element, period=obs.period, value=obs.value)
            for obs in consumer_price_index
        ]
        VietnamStatistics.objects.bulk_create(entities)

        self.stdout.write(
            self.style.SUCCESS("Successfully fetched and stored Vietnam CPI data.")
        )
