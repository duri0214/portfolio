import os

import requests
from django.core.management.base import BaseCommand

from soil_analysis.models import JmaWeatherCode


class Command(BaseCommand):
    help = 'Download weather code icons from JMA API'

    def handle(self, *args, **options):
        # Get all weather codes
        weather_codes = JmaWeatherCode.objects.all()

        # Create icons directory if it doesn't exist
        icons_dir = 'static/icons/weather'
        os.makedirs(icons_dir, exist_ok=True)

        for weather_code in weather_codes:
            # Download icon
            icon_url = f"https://www.jma.go.jp/bosai/forecast/img/{weather_code.code}.svg"
            response = requests.get(icon_url)

            if response.status_code == 200:
                # Save icon file
                icon_path = os.path.join(icons_dir, f"{weather_code.code}.svg")
                with open(icon_path, 'wb') as f:
                    f.write(response.content)

                self.stdout.write(
                    self.style.SUCCESS(f'Successfully downloaded icon for weather code {weather_code.code}')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to download icon for weather code {weather_code.code}')
                )
