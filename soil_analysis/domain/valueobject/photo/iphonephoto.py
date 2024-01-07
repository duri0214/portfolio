import io
import os
import re

import exifread

from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.photo.basephoto import BasePhoto


class IphonePhoto(BasePhoto):
    def __init__(self, photo_path: str):
        self.filepath = photo_path
        self.filename = os.path.basename(photo_path)
        self.exif_data = self._extract_exif_data()
        self.date = self._extract_date()
        self.location = self._extract_location()
        self.azimuth = self._extract_azimuth()

    def _extract_exif_data(self) -> dict:
        with open(self.filepath, "rb") as f:
            file_data = f.read()
        tags = exifread.process_file(io.BytesIO(file_data))

        exif_data = {}
        for tag, value in tags.items():
            tag_name = tag.replace('EXIF ', '')
            exif_data[tag_name] = value

        return exif_data

    def _extract_date(self) -> str:
        gps_date = self.exif_data.get('Image DateTime')
        if gps_date is None:
            raise ValueError("Invalid Image DateTime value: None")

        match = re.search(r'\d{4}:\d{2}:\d{2}', str(gps_date))
        if match:
            capture_date = match.group().replace(':', '-')
            return capture_date

        raise ValueError("Invalid GPS date format")

    def _extract_location(self) -> CaptureLocation:
        gps_longitude = self.exif_data.get('GPS GPSLongitude')
        if gps_longitude is None:
            raise ValueError("Invalid GPSLongitude value: None")
        gps_latitude = self.exif_data.get('GPS GPSLatitude')
        if gps_latitude is None:
            raise ValueError("Invalid GPSLatitude value: None")

        return CaptureLocation(self._convert_to_degrees(gps_longitude), self._convert_to_degrees(gps_latitude))

    def _extract_azimuth(self) -> float:
        gps_img_direction = self.exif_data.get('GPS GPSImgDirection')
        if gps_img_direction is None:
            raise ValueError("Invalid GPSImgDirection value: None")
        temp = str(gps_img_direction).split('/')

        return float(temp[0]) / float(temp[1])

    @staticmethod
    def _convert_to_degrees(coord: exifread.classes.IfdTag):
        degrees = float(coord.values[0].num) / float(coord.values[0].den)
        minutes = float(coord.values[1].num) / float(coord.values[1].den)
        seconds = float(coord.values[2].num) / float(coord.values[2].den)

        return degrees + (minutes / 60.0) + (seconds / 3600.0)
