import tempfile
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase, override_settings

from lib.zipfileservice import ZipFileService


class ZipFileServiceTestCase(TestCase):
    @staticmethod
    def create_temp_zip_file(dir_path: Path, filename: str, filedata: bytes) -> Path:
        zip_file_path = dir_path / filename
        zip_file = zipfile.ZipFile(str(zip_file_path), "w")
        zip_file.writestr("test_file.txt", filedata)
        zip_file.close()
        return zip_file_path

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_handle_uploaded_zip(self):
        # Create a temp ZIP file
        temp_dir = Path(tempfile.gettempdir())
        file_data = b"Test file data"
        zip_file_path = self.create_temp_zip_file(temp_dir, "archive.zip", file_data)

        # Convert the ZIP file to InMemoryUploadedFile
        with open(str(zip_file_path), "rb") as f:
            file_data = f.read()
        uploaded_file = InMemoryUploadedFile(
            ContentFile(file_data),
            field_name="file",
            name="archive.zip",
            content_type="application/zip",
            size=len(file_data),
            charset=None,
        )

        result = ZipFileService.handle_uploaded_zip(uploaded_file, "test_app_name")

        # Validate the result
        expected_upload_folder = Path(tempfile.gettempdir()) / "test_app_name"
        self.assertEqual(str(expected_upload_folder), str(result))
        self.assertTrue(expected_upload_folder.exists())
