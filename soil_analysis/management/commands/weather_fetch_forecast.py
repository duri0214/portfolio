from datetime import datetime

import requests
from django.core.management.base import BaseCommand

from soil_analysis.models import JmaWeather, JmaArea


class Command(BaseCommand):
    help = 'Fetch weather forecast data from JMA API'

    def handle(self, *args, **options):
        # JMA API endpoint for weather forecast
        url = "https://www.jma.go.jp/bosai/forecast/data/forecast/"

        # Get all areas
        areas = JmaArea.objects.all()

        for area in areas:
            try:
                # Fetch forecast data for each area
                response = requests.get(f"{url}{area.code}.json")
                if response.status_code == 200:
                    data = response.json()

                    # Process and save weather data
                    for forecast in data:
                        # Extract relevant weather information
                        weather_data = {
                            'area': area,
                            'forecast_date': datetime.now().date(),
                            'weather_code': forecast.get('weatherCode'),
                            'temperature_max': forecast.get('tempMax'),
                            'temperature_min': forecast.get('tempMin'),
                            'precipitation': forecast.get('precipitation'),
                        }

                        # Create or update weather record
                        JmaWeather.objects.update_or_create(
                            area=area,
                            forecast_date=weather_data['forecast_date'],
                            defaults=weather_data
                        )

                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully fetched forecast for {area.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to fetch forecast for {area.name}')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing area {area.name}: {str(e)}')
                )
