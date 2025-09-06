import os
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse


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
    def _convert_to_cp932(folder_name: str) -> str:
        """
        WindowsでZipファイルを作成すると、文字化けが起こるので対応

        See Also: https://qiita.com/tohka383/items/b72970b295cbc4baf5ab
        """
        return folder_name.encode("cp437").decode("cp932")

    @staticmethod
    def get_user_download_dir() -> Path:
        """
        ユーザーのダウンロードディレクトリを取得する
        """
        # OSに応じてダウンロードディレクトリを取得
        try:
            # Windowsの場合
            if os.name == "nt":
                import winreg

                sub_key = (
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
                )
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                    download_dir = winreg.QueryValueEx(
                        key, "{374DE290-123F-4565-9164-39C4925E467B}"
                    )[0]
                    return Path(download_dir)

            # macOSの場合
            elif os.name == "posix" and os.uname().sysname == "Darwin":
                return Path.home() / "Downloads"

            # Linuxの場合
            elif os.name == "posix":
                return Path.home() / "Downloads"
        except (
            ImportError,
            FileNotFoundError,
            PermissionError,
            OSError,
            AttributeError,
        ) as e:
            # 取得できない場合はデフォルトのテンポラリディレクトリを使用
            print(f"ダウンロードディレクトリの取得に失敗: {e}")

        # どれにも当てはまらない場合や例外が発生した場合はテンポラリディレクトリを使用
        return Path(tempfile.gettempdir())

    @staticmethod
    def create_zip_from_dir(
        source_dir: Path, zip_filename: str = None, output_location: str = "temp"
    ) -> Path:
        """
        ディレクトリをZIPファイルに圧縮する

        Args:
            source_dir: 圧縮するディレクトリのパス
            zip_filename: 作成するZIPファイルの名前（指定しない場合は自動生成）
            output_location: 出力先（"temp": 一時ディレクトリ, "download": ダウンロードディレクトリ）

        Returns:
            作成されたZIPファイルのパス
        """
        source_dir_path = Path(source_dir)

        # ソースディレクトリの存在確認
        if not source_dir_path.exists():
            raise FileNotFoundError(f"ソースディレクトリが存在しません: {source_dir}")

        # ZIPファイル名が指定されていない場合、ディレクトリ名と日時から生成
        if not zip_filename:
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"{source_dir_path.name}_{now}.zip"

        # 出力先を決定
        if output_location == "download":
            output_dir = ZipFileService.get_user_download_dir()
        else:
            output_dir = Path(tempfile.gettempdir())

        zip_file_path = output_dir / zip_filename

        # ZIPファイルを作成
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_dir_path):
                for file in files:
                    file_path = Path(root) / file
                    # アーカイブ内での相対パスを計算
                    archive_path = file_path.relative_to(source_dir_path.parent)
                    zipf.write(file_path, archive_path)

        return zip_file_path

    @staticmethod
    def serve_zip_file(
        zip_file_path: Path, download_filename: str = None
    ) -> FileResponse:
        """
        ZIPファイルをダウンロードさせるためのFileResponseを返す

        Args:
            zip_file_path: ダウンロードさせるZIPファイルのパス
            download_filename: ダウンロード時のファイル名（指定しない場合はzip_file_pathのファイル名）

        Returns:
            ダウンロード用のFileResponse
        """
        if not zip_file_path.exists():
            raise FileNotFoundError(f"ZIPファイルが存在しません: {zip_file_path}")

        # ダウンロード時のファイル名を設定
        if not download_filename:
            download_filename = zip_file_path.name

        # FileResponseを作成
        response = FileResponse(
            open(zip_file_path, "rb"), as_attachment=True, filename=download_filename
        )
        response["Content-Type"] = "application/zip"
        return response

    @staticmethod
    def create_and_serve_zip(
        source_dir: Path, zip_filename: str = None, cleanup: bool = True
    ) -> FileResponse:
        """
        ディレクトリをZIP化してダウンロードさせる

        Args:
            source_dir: 圧縮するディレクトリのパス
            zip_filename: ダウンロード時のZIPファイル名（指定しない場合は自動生成）
            cleanup: 処理完了後に一時ファイルを削除するかどうか

        Returns:
            ダウンロード用のFileResponse
        """
        # ディレクトリをZIP化（Webアプリ用なので一時ディレクトリを使用）
        zip_file_path = ZipFileService.create_zip_from_dir(
            source_dir, zip_filename, output_location="temp"
        )

        # ダウンロード用のレスポンスを作成
        response = ZipFileService.serve_zip_file(zip_file_path, zip_filename)

        # 後処理（ZIPファイルの削除）を設定
        if cleanup:

            def delete_file():
                # レスポンスが送信された後にファイルを削除するために少し待機
                time.sleep(2)
                try:
                    if zip_file_path.exists():
                        zip_file_path.unlink()
                except (PermissionError, OSError, FileNotFoundError) as e:
                    # 削除中にエラーが発生しても処理を続行
                    print(f"ZIPファイル削除中にエラーが発生: {e}")

            # 非同期で削除処理を実行する（本来はceleryなどを使うべきだが、簡易実装）
            import threading

            threading.Thread(target=delete_file).start()

        return response
