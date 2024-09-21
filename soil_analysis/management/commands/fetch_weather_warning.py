import requests
from django.core.management import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import WarningData
from soil_analysis.models import JmaWarning, JmaRegion, Land

LATEST_WARNING = 0
M_TARGET_WARNINGS = {
    "02": "暴風雪警報",
    "03": "大雨警報",
    "04": "洪水警報",
    "05": "暴風警報",
    "06": "大雪警報",
    "07": "波浪警報",
    "08": "高潮警報",
    "10": "大雨注意報",
    "12": "大雪注意報",
    "13": "風雪注意報",
    "14": "雷注意報",
    "15": "強風注意報",
    "16": "波浪注意報",
    "17": "融雪注意報",
    "18": "洪水注意報",
    "19": "高潮注意報",
    "20": "濃霧注意報",
    "21": "乾燥注意報",
    "22": "なだれ注意報",
    "23": "低温注意報",
    "24": "霜注意報",
    "25": "着氷注意報",
    "26": "着雪注意報",
    "27": "その他の注意報",
    "32": "暴風雪特別警報",
    "33": "大雨特別警報",
    "35": "暴風特別警報",
    "36": "大雪特別警報",
    "37": "波浪特別警報",
    "38": "高潮特別警報",
}


def get_data(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


class Command(BaseCommand):
    help = "get weather warning"

    def handle(self, *args, **options):
        jma_prefecture_ids = Land.objects.values_list(
            "jma_city__jma_region__jma_prefecture__code", flat=True
        ).distinct()

        if not jma_prefecture_ids:
            raise Exception("facility is empty")

        region_master = {x.code: x for x in JmaRegion.objects.all()}

        JmaWarning.objects.all().delete()
        jma_warning_list: list[JmaWarning] = []
        for prefecture_id in jma_prefecture_ids:
            url = (
                f"https://www.jma.go.jp/bosai/warning/data/warning/{prefecture_id}.json"
            )
            latest_warning_data = get_data(url)["areaTypes"][LATEST_WARNING]

            for region_data in latest_warning_data["areas"]:
                region_code = region_data["code"]

                warning_data_list = [
                    WarningData(code=x["code"], status=x["status"])
                    for x in region_data["warnings"]
                    if "code" in x
                ]

                if not warning_data_list:
                    continue

                warnings: list[str] = list(
                    set(
                        [
                            M_TARGET_WARNINGS[warning_data.code]
                            for warning_data in warning_data_list
                        ]
                    )
                )
                jma_warning_list.append(
                    JmaWarning(
                        jma_region=region_master.get(region_code),
                        warnings=",".join(warnings),
                    )
                )
            JmaWarning.objects.bulk_create(jma_warning_list)

        self.stdout.write(
            self.style.SUCCESS("weather warning data retrieve has been completed.")
        )
