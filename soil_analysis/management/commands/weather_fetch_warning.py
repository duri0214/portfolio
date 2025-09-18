from datetime import datetime

import requests
from django.core.management.base import BaseCommand

from soil_analysis.models import JmaWarning, JmaArea


class Command(BaseCommand):
    help = 'Fetch weather warning data from JMA API'

    def handle(self, *args, **options):
        # JMA API endpoint for weather warnings
        url = "https://www.jma.go.jp/bosai/forecast/data/warn/"

        # Get all areas
        areas = JmaArea.objects.all()

        for area in areas:
            try:
                # Fetch warning data for each area
                response = requests.get(f"{url}{area.code}.json")
                if response.status_code == 200:
                    data = response.json()

                    # Process and save warning data
                    for warning in data:
                        # Extract relevant warning information
                        warning_data = {
                            'area': area,
                            'warning_date': datetime.now().date(),
                            'warning_type': warning.get('type'),
                            'warning_level': warning.get('level'),
                            'description': warning.get('description', ''),
                        }

                        # Create or update warning record
                        JmaWarning.objects.update_or_create(
                            area=area,
                            warning_date=warning_data['warning_date'],
                            warning_type=warning_data['warning_type'],
                            defaults=warning_data
                        )

                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully fetched warnings for {area.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Failed to fetch warnings for {area.name}')
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing area {area.name}: {str(e)}')
                )
