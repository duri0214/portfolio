import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from lib.log_service import LogService
from linebot_engine.models import UserProfile, Message


class Command(BaseCommand):
    help = "Cleanup for media files not used by UserProfile and Message models"

    def handle(self, *args, **options):
        log_service = LogService("./result.log")
        search_dir = os.path.join(settings.MEDIA_ROOT, "linebot_engine", "images")

        used_files = []
        for model in [UserProfile, Message]:
            query = model.objects.all()
            for record in query:
                if record.picture:
                    used_files.append(
                        os.path.join(settings.MEDIA_ROOT, record.picture.name)
                    )

        for filepath in Path(search_dir).rglob("*"):
            if str(filepath) not in used_files:
                os.remove(str(filepath))
                print(f"Removed {filepath}")
                log_service.write(f"Removed {filepath}")

        log_service.write("monthly_garbage_collection is done.")
