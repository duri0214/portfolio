import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile


class ZipFileService:
    @staticmethod
    def handle_uploaded_zip(file: InMemoryUploadedFile, app_name: str) -> Path:
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
        target_dir_path.mkdir(parents=True, exist_ok=True)

        zip_files = source_dir_path.glob("*.zip")
        for zip_file in zip_files:
            with zipfile.ZipFile(str(zip_file), "r") as zipf:
                zipf.extractall(str(target_dir_path))

    @staticmethod
    def _convert_to_cp932(folder_name: str) -> str:
        """
        WindowsでZipファイルを作成すると、文字化けが起こるので対応

        See Also: https://qiita.com/tohka383/items/b72970b295cbc4baf5ab
        """
        return folder_name.encode("cp437").decode("cp932")
