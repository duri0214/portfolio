import io
import os
import re

import exifread

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation


class ExifReader:
    """EXIFデータを読み取るクラス"""

    @staticmethod
    def read_exif_data(file_path: str) -> dict:
        """ファイルからEXIFデータを読み取る"""
        with open(file_path, "rb") as f:
            file_data = f.read()
        tags = exifread.process_file(io.BytesIO(file_data))

        exif_data = {}
        for tag, value in tags.items():
            tag_name = tag.replace("EXIF ", "")
            exif_data[tag_name] = value

        return exif_data


class BasePhoto:
    """写真のEXIFデータを処理する抽象基底クラス"""

    def __init__(self, photo_path: str, exif_reader=None):
        """
        初期化

        Args:
            photo_path: 写真ファイルのパス
            exif_reader: EXIFデータを読み取るためのオブジェクト（テスト用のモック注入可能）
        """
        self.filepath = photo_path
        self.filename = os.path.basename(photo_path)
        self._exif_reader = (
            exif_reader or ExifReader()
        )  # デフォルトのリーダーか注入されたリーダーを使用
        self.exif_data = self._extract_exif_data()
        self.date = self._extract_date()
        self.location = self._extract_location()

    def _extract_exif_data(self) -> dict:
        """写真ファイルからEXIFデータを抽出する"""
        return self._exif_reader.read_exif_data(self.filepath)

    def _extract_date(self) -> str:
        """EXIFデータから撮影日時を抽出する"""
        gps_date = self.exif_data.get("Image DateTime")
        if gps_date is None:
            raise ValueError("Invalid Image DateTime value: None")

        match = re.search(r"\d{4}:\d{2}:\d{2}", str(gps_date))
        if match:
            capture_date = match.group().replace(":", "-")
            return capture_date

        raise ValueError("Invalid GPS date format")

    def _extract_location(self) -> CaptureLocation:
        """EXIFデータから位置情報を抽出する"""
        gps_longitude = self.exif_data.get("GPS GPSLongitude")
        if gps_longitude is None:
            raise ValueError("Invalid GPSLongitude value: None")
        gps_latitude = self.exif_data.get("GPS GPSLatitude")
        if gps_latitude is None:
            raise ValueError("Invalid GPSLatitude value: None")

        return CaptureLocation(
            XarvioCoord(
                longitude=self._convert_to_degrees(gps_longitude),
                latitude=self._convert_to_degrees(gps_latitude),
            )
        )

    @staticmethod
    def _convert_to_degrees(coord: exifread.classes.IfdTag) -> float:
        """座標を度に変換する"""
        degrees = float(coord.values[0].num) / float(coord.values[0].den)
        minutes = float(coord.values[1].num) / float(coord.values[1].den)
        seconds = float(coord.values[2].num) / float(coord.values[2].den)

        return degrees + (minutes / 60.0) + (seconds / 3600.0)


class AndroidPhoto(BasePhoto):
    """Androidで撮影された写真を処理するクラス"""

    # 全ての機能が基底クラスにあるため、追加実装は不要
    pass


class IphonePhoto(BasePhoto):
    """iPhoneで撮影された写真を処理するクラス"""

    def __init__(self, photo_path: str, exif_reader=None):
        super().__init__(photo_path, exif_reader)
        self.azimuth = self._extract_azimuth()

    def _extract_azimuth(self) -> float:
        """EXIFデータから方位角を抽出する"""
        gps_img_direction = self.exif_data.get("GPS GPSImgDirection")
        if gps_img_direction is None:
            raise ValueError("Invalid GPSImgDirection value: None")
        temp = str(gps_img_direction).split("/")

        return float(temp[0]) / float(temp[1])
