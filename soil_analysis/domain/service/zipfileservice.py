import os
import zipfile

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile


class ZipFileService:
    @staticmethod
    def handle_uploaded_zip(file: InMemoryUploadedFile) -> str:
        """
        アップロードされたファイルを一時フォルダ media/soilhardness に保存
        Args:
            file: requestから受け取ったファイル
        """
        # 解凍場所の用意
        upload_folder = os.path.join(settings.MEDIA_ROOT, 'soilhardness')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        # ファイルを保存
        destination_zip_path = os.path.join(upload_folder, 'uploaded.zip')
        with open(destination_zip_path, 'wb+') as z:
            for chunk in file.chunks():
                z.write(chunk)

        # ファイルを解凍
        with zipfile.ZipFile(destination_zip_path) as z:
            for info in z.infolist():
                info.filename = ZipFileService._convert_to_cp932(info.filename)
                z.extract(info, path=upload_folder)

        return upload_folder

    @staticmethod
    def _convert_to_cp932(folder_name: str) -> str:
        """
        WindowsでZipファイルを作成すると、文字化けが起こるので対応
        TODO: テストが作れない（cp437で壊れたzipfileが再現できないので、公開サーバいったときに失敗する可能性あり）
         南さんのパソコンでやっているあいだは大丈夫だと思う

        See Also: https://qiita.com/tohka383/items/b72970b295cbc4baf5ab
        """
        return folder_name.encode('cp437').decode('cp932')
