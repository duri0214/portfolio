import csv
import re

from django.core.management.base import BaseCommand

from soil_analysis.domain.valueobject.weather.weather import WeatherCodeRaw
from soil_analysis.models import JmaWeather, JmaWeatherCode


class Command(BaseCommand):
    help = "Import jma weather code master from data."

    def handle(self, *args, **options):
        """
        Handles the import of JmaWeatherCode objects from a formatted data string.

        See Also: `view-source:https://www.jma.go.jp/bosai/forecast/`

        Args:
            *args: Additional positional arguments (unused).
            **options: Additional keyword arguments (unused).
        """
        data = '{100:["100.svg","500.svg","100","\u6674","CLEAR"],}'

        JmaWeather.objects.all().delete()

        # Remove empty entries (ケツカンマを無視する)
        entries = re.split(r",(?=\d+:)", data.strip("{}"))

        weather_code_list = []
        for entry in entries:
            key, values = entry.split(":")

            # Remove the brackets from the values and split by comma safely
            values = values.strip("[]")
            values = next(csv.reader([values]))

            weather_code_raw = WeatherCodeRaw(key, *values)
            weather_code_list.append(weather_code_raw)

        jma_weather_code_objects = [
            JmaWeatherCode(
                code=x.code,
                image=x.image_day,
                summary_code=x.summary_code,
                name=x.name,
                name_en=x.name_en,
            )
            for x in weather_code_list
        ]

        JmaWeatherCode.objects.bulk_create(jma_weather_code_objects)

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported all jma weather code master from data."
            )
        )
