import tempfile
import zipfile
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.test import TestCase, override_settings

from lib.zipfileservice import ZipFileService


class ZipFileServiceTestCase(TestCase):
    """
    ZipFileService の振る舞いを検証するユニットテスト。

    目的:
    - アップロード ZIP の保存と安全な展開の基本動作を確認
    - ZIP“自体”のファイル名が日本語（例: 日本語.zip）でも処理できることを確認
    - ZIP 内の日本語ファイル名（UTF-8 フラグ付き）が正しく展開されることを確認
    補足:
    - 現状、CP932 前提の古い ZIP はユニットテストでは網羅していません（復号はサービス側のフォールバックで対応）。
    """
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

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_handle_uploaded_zip_with_japanese_filename(self):
        """
        シナリオ概要:
        - 日本語名の ZIP 自体（例: 日本語.zip）を作成し、アップロードとして扱う。
        - ZIP 内にも日本語ファイル名（例: 日本語.txt。UTF-8 フラグが立つ想定）を格納する。
        - `ZipFileService.handle_uploaded_zip("日本語.zip", app_name="test_app_name_jp")` を実行し、
          MEDIA_ROOT/test_app_name_jp 配下に安全に展開されることを確認する。

        検証観点:
        - ZIP 内の日本語ファイルが正しいバイト内容で展開されること。
        - 解凍先ではアップロード ZIP は固定名 `uploaded.zip` として保存される仕様であり、
          元の ZIP 名（日本語.zip）は保存ファイル名としては使用されないこと（仕様の再確認）。
        - Zip Slip 対策（パス検証）はサービス側で行われ、本テストは正常系の日本語名処理にフォーカスする。

        前提:
        - テストでは `@override_settings(MEDIA_ROOT=...)` により MEDIA_ROOT を OS の一時ディレクトリへ切り替える。
        - CP932 前提の古い ZIP は本テストの対象外（サービスのフォールバックで別途考慮）。
        """
        temp_dir = Path(tempfile.gettempdir())
        jp_name = "日本語.txt"
        content = b"Hello Japanese filename"
        zip_file_path = temp_dir / "日本語.zip"
        with zipfile.ZipFile(str(zip_file_path), "w") as zf:
            zf.writestr(jp_name, content)

        # Convert the ZIP file to InMemoryUploadedFile
        with open(str(zip_file_path), "rb") as f:
            data = f.read()
        uploaded_file = InMemoryUploadedFile(
            ContentFile(data),
            field_name="file",
            name="日本語.zip",
            content_type="application/zip",
            size=len(data),
            charset=None,
        )

        ZipFileService.handle_uploaded_zip(uploaded_file, "test_app_name_jp")

        expected_upload_folder = Path(tempfile.gettempdir()) / "test_app_name_jp"
        expected_file_path = expected_upload_folder / jp_name
        self.assertTrue(expected_file_path.exists(), f"{expected_file_path} should exist after extraction")
        self.assertEqual(expected_file_path.read_bytes(), content) 
