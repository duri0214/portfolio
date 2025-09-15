import os
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpResponse


class ZipFileService:
    @staticmethod
    def handle_uploaded_zip(file: UploadedFile, app_name: str) -> Path:
        """
        アップロードされたファイルを一時フォルダ media/{app_name} に保存
        Args:
            file: requestから受け取ったファイル
            app_name: アプリ名
        """
        # 解凍場所の用意
        upload_folder = Path(settings.MEDIA_ROOT) / app_name
        upload_folder.mkdir(parents=True, exist_ok=True)

        # ファイルを保存
        destination_zip_path = upload_folder / "uploaded.zip"
        with destination_zip_path.open("wb+") as z:
            for chunk in file.chunks():
                z.write(chunk)

        # ファイルを解凍
        with zipfile.ZipFile(destination_zip_path) as z:
            for info in z.infolist():
                info.filename = ZipFileService._convert_to_cp932(info.filename)
                z.extract(info, path=str(upload_folder))

        return upload_folder

    @staticmethod
    def extract_zip_files(source_dir: Path, target_dir: Path):
        """
        ソースディレクトリからのすべてのzipファイルをターゲットディレクトリに解凍します。
        """
        source_dir_path = Path(source_dir)
        target_dir_path = Path(target_dir)

        # Check if the source directory exists
        if not source_dir_path.exists():
            raise FileNotFoundError(f"The source directory {source_dir} does not exist")

        # Check if the target directory exists
        if not target_dir_path.exists():
            raise FileNotFoundError(f"The target directory {target_dir} does not exist")

        zip_files = source_dir_path.glob("*.zip")
        for zip_file in zip_files:
            with zipfile.ZipFile(str(zip_file), "r") as zip_f:
                zip_f.extractall(str(target_dir_path))

    @staticmethod
    def create_zip_download(
        folder_path: str, filename: str = "download.zip"
    ) -> HttpResponse:
        """
        フォルダをZIP化してダウンロードレスポンスを作成
        """
        import io

        # メモリ上でZIPファイルを作成
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arc_name)

        # HTTPレスポンスを作成
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    @staticmethod
    def _convert_to_cp932(folder_name: str) -> str:
        """
        WindowsでZipファイルを作成すると、文字化けが起こるので対応

        See Also: https://qiita.com/tohka383/items/b72970b295cbc4baf5ab
        """
        try:
            return folder_name.encode("cp437").decode("cp932")
        except (UnicodeEncodeError, UnicodeDecodeError):
            # エンコーディング変換に失敗した場合は元のファイル名を返す
            return folder_name
