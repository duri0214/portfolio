import csv
import re

from django.core.management.base import BaseCommand

from soil_analysis.domain.valueobject.weather.weather import WeatherCodeRaw
from soil_analysis.models import (
    JmaWeatherCode,
)


class Command(BaseCommand):
    help = "Import jma weather code master from manual data."

    def handle(self, *args, **options):
        """
        Args:
            *args: Additional positional arguments.
            **options: Additional keyword arguments.
        """
        data = '{100:["100.svg","500.svg","100","\u6674","CLEAR"],}'

        # Clear
        JmaWeatherCode.objects.all().delete()

        # Use a regular expression to split by outer commas
        entries = re.split(r",(?=\d+:)", data.strip("{}"))

        weather_code_list = []
        for entry in entries:
            key, values = entry.split(":")

            # Remove the brackets from the values and split by comma safely
            values = values.strip("[]")
            values = next(csv.reader([values]))

            weather_code_raw = WeatherCodeRaw(key, *values)
            weather_code_list.append(weather_code_raw)

        jma_weather_code_list = [
            JmaWeatherCode(
                code=x.code,
                image=x.image_day,
                summary_code=x.summary_code,
                name=x.name,
                name_en=x.name_en,
            )
            for x in weather_code_list
        ]
        JmaWeatherCode.objects.bulk_create(jma_weather_code_list)

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported all jma weather code master from manual data."
            )
        )
