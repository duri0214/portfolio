import sys

import requests
from django.core.management.base import BaseCommand

from soil_analysis.domain.valueobject.weather.jma import JmaConstGeographicArea
from soil_analysis.models import (
    JmaArea,
    JmaRegion,
    JmaPrefecture,
    JmaCity,
    JmaAmedas,
)


def get_data_from_url(url: str):
    try:
        # Obtain the response from the URL
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(
            f"データの取得でエラーが発生しました。URL: {url} エラー詳細: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    # Parse the JSON response into a Python dictionary
    return response.json()


class Command(BaseCommand):
    help = "Import jma const master from data."

    def handle(self, *args, **options):
        """
        Args:
            *args: Additional positional arguments (unused).
            **options: Additional keyword arguments (unused).
        """
        # Part1: from const
        url = "https://www.jma.go.jp/bosai/common/const/area.json"
        raw_data = get_data_from_url(url)

        # Create and save JmaArea: 010600 近畿地方
        JmaArea.objects.all().delete()
        jma_area_list = [
            JmaConstGeographicArea(
                code=code,
                name=data["name"],
                children=data.get("children", []),
                parent=data.get("parent"),
            )
            for code, data in raw_data["centers"].items()
        ]
        JmaArea.objects.bulk_create(
            [JmaArea(code=vo.code, name=vo.name) for vo in jma_area_list]
        )
        jma_area_cache = {obj.code: obj for obj in JmaArea.objects.all()}

        # Create and save JmaPrefecture: 280000 兵庫県
        JmaPrefecture.objects.all().delete()
        jma_prefecture_list = [
            JmaConstGeographicArea(
                code=code,
                name=data["name"],
                children=data.get("children", []),
                parent=data.get("parent"),
            )
            for code, data in raw_data["offices"].items()
        ]
        JmaPrefecture.objects.bulk_create(
            [
                JmaPrefecture(
                    code=vo.code, name=vo.name, jma_area=jma_area_cache.get(vo.parent)
                )
                for vo in jma_prefecture_list
            ]
        )
        jma_prefecture_cache = {obj.code: obj for obj in JmaPrefecture.objects.all()}

        # Create and save JmaRegion: 280010 南部
        JmaRegion.objects.all().delete()
        jma_region_list = [
            JmaConstGeographicArea(
                code=code,
                name=data["name"],
                children=data.get("children", []),
                parent=data.get("parent"),
            )
            for code, data in raw_data["class10s"].items()
        ]
        JmaRegion.objects.bulk_create(
            [
                JmaRegion(
                    code=vo.code,
                    name=vo.name,
                    jma_prefecture=jma_prefecture_cache.get(vo.parent),
                )
                for vo in jma_region_list
            ]
        )
        jma_region_cache = {obj.code: obj for obj in JmaRegion.objects.all()}

        # Create JmaCityGroup
        jma_city_group_list = [
            JmaConstGeographicArea(
                code=code,
                name=data["name"],
                children=data.get("children", []),
                parent=data.get("parent"),
            )
            for code, data in raw_data["class15s"].items()
        ]
        jma_city_group_cache = {
            jma_city_group.code: jma_city_group
            for jma_city_group in jma_city_group_list
        }

        # Create and save JmaCity with parents via JmaCityGroup: 2820100 姫路市
        JmaCity.objects.all().delete()
        jma_city_list = [
            JmaConstGeographicArea(
                code=code,
                name=data["name"],
                children=data.get("children", []),
                parent=data.get("parent"),
            )
            for code, data in raw_data["class20s"].items()
        ]
        JmaCity.objects.bulk_create(
            [
                JmaCity(
                    code=vo.code,
                    name=vo.name,
                    jma_region=jma_region_cache.get(
                        jma_city_group_cache.get(vo.parent).parent
                    ),
                )
                for vo in jma_city_list
            ]
        )

        # Part2: from forecast_area.json
        url = "https://www.jma.go.jp/bosai/forecast/const/forecast_area.json"
        raw_data = get_data_from_url(url)

        JmaAmedas.objects.all().delete()
        jma_amedas_list = []
        for prefecture_code, entries in raw_data.items():
            for entry in entries:
                region_code = entry["class10"]
                for amedas_code in entry["amedas"]:
                    jma_amedas_list.append(
                        JmaAmedas(
                            code=amedas_code,
                            jma_region=jma_region_cache.get(region_code),
                        )
                    )
        JmaAmedas.objects.bulk_create(jma_amedas_list)

        self.stdout.write(
            self.style.SUCCESS("jma const master data import has been completed.")
        )
