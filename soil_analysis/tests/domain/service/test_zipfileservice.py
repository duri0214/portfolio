import os
import tempfile
import zipfile

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase, override_settings

from soil_analysis.domain.service.zipfileservice import ZipFileService


class ZipFileServiceTestCase(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_handle_uploaded_zip(self):
        # ZIP ファイルを作成
        tmpdir = tempfile.mkdtemp()
        zip_fn = os.path.join(tmpdir, 'archive.zip')
        zip_obj = zipfile.ZipFile(zip_fn, 'w')

        # ZIP ファイルに追加
        file_data = b'Test file data'
        zip_obj.writestr('test_file.txt', file_data)
        zip_obj.close()

        # ZIP ファイルを InMemoryUploadedFile に変換する
        with open(zip_fn, 'rb') as f:
            file_data = f.read()
        uploaded_file = InMemoryUploadedFile(
            ContentFile(file_data),
            field_name='file',
            name='archive.zip',
            content_type='application/zip',
            size=len(file_data),
            charset=None,
        )

        result = ZipFileService.handle_uploaded_zip(uploaded_file)

        # media/soilhardness と一致する
        expected_upload_folder = os.path.join(tempfile.gettempdir(), 'soilhardness')
        self.assertEqual(expected_upload_folder, result)
        self.assertTrue(os.path.exists(expected_upload_folder))
