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
        entries = [entry for entry in data.strip("{}").split(",") if entry]

        weather_code_list = []
        for entry in entries:
            key, values = entry.split(":")
            key = key.strip()
            values = eval(values.strip())
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
