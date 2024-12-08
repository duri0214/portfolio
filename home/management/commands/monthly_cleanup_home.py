import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from home.models import Post
from lib.log_service import LogService


class Command(BaseCommand):
    help = "Cleanup for media files not used by Post model"

    def handle(self, *args, **options):
        log_service = LogService("./result.log")
        search_dir = os.path.join(settings.MEDIA_ROOT, "home", "posts")

        used_files = []
        query = Post.objects.all()
        for record in query:
            if record.image:
                used_files.append(os.path.join(settings.MEDIA_ROOT, record.image.name))

        for filepath in Path(search_dir).rglob("*"):
            if str(filepath) not in used_files:
                os.remove(str(filepath))
                print(f"Removed {filepath}")
                log_service.write(f"Removed {filepath}")

        log_service.write("monthly_garbage_collection is done.")
