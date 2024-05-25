import shutil
from pathlib import Path

from django.core.management import call_command

from lib.zipfileservice import ZipFileService


class UploadService:
    def __init__(self, request):
        self.request = request
        self.app_name = request.resolver_match.app_name

    def upload(self):
        upload_folder = ZipFileService.handle_uploaded_zip(
            self.request.FILES["file"], self.app_name
        )
        self.execute_command_and_cleanup(upload_folder)

    @staticmethod
    def execute_command_and_cleanup(upload_folder: Path):
        if upload_folder.exists():
            call_command("import_edinet_code", str(upload_folder))
            shutil.rmtree(upload_folder)
