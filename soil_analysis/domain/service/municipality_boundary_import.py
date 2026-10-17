"""国土数値情報の行政区域Shape ZIPを検証して保存するサービス。"""

from __future__ import annotations

import hashlib
import re
import tempfile
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import BinaryIO

import shapefile
from django.db import transaction
from django.utils import timezone

from lib.zipfileservice import UnsafeZipPathError, ZipFileService
from soil_analysis.domain.repository.municipality_soil import (
    MunicipalitySoilRepository,
)
from soil_analysis.models import MunicipalityBoundaryDataset


class MunicipalityBoundaryImportError(Exception):
    """利用者に安全に伝えられる市区町村境界の検証・取込エラー。"""


class MunicipalityBoundaryImportService:
    """国土数値情報N03の全国版を、市区町村境界データ版として取り込む。"""

    REQUIRED_FIELD_NAMES = ("N03_001", "N03_004", "N03_007")
    NATIONAL_PREFECTURE_CODES = frozenset(f"{code:02d}" for code in range(1, 48))
    MAX_UNCOMPRESSED_BYTES = 2_500 * 1024 * 1024
    BATCH_SIZE = 200

    @classmethod
    def import_boundary_from_zip(
        cls, source: BinaryIO | Path, source_name: str | None = None
    ) -> MunicipalityBoundaryDataset:
        """全国版N03のZIPを検証し、すべて保存できた場合だけ有効版を切り替える。"""
        with tempfile.TemporaryDirectory(prefix="municipality-boundary-") as directory:
            temporary_path = Path(directory)
            zip_path, zip_name, digest = cls._copy_zip_source(
                source, temporary_path, source_name
            )
            extract_path = temporary_path / "extract"
            cls._extract_zip_file(zip_path, extract_path)
            shape_path = cls._find_shape_path(extract_path)
            reader = shapefile.Reader(
                str(shape_path), encoding=cls._get_dbf_encoding(shape_path)
            )
            try:
                field_names = [field[0] for field in reader.fields[1:]]
                cls._validate_shape(reader, field_names, shape_path)
                municipalities, feature_count = cls._build_municipalities(
                    reader, field_names
                )
            finally:
                reader.close()

            cls._validate_national_coverage(municipalities)
            source_crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8")
            source_date = cls._source_date_from_name(zip_name)
            with transaction.atomic():
                MunicipalitySoilRepository.deactivate_active_boundary_datasets()
                dataset = MunicipalitySoilRepository.create_boundary_dataset(
                    source_file_name=zip_name,
                    source_sha256=digest,
                    source_crs=source_crs,
                    source_date=source_date,
                    feature_count=feature_count,
                    municipality_count=len(municipalities),
                    is_active=True,
                    imported_at=timezone.now(),
                )
                for start in range(0, len(municipalities), cls.BATCH_SIZE):
                    MunicipalitySoilRepository.bulk_create_municipalities(
                        dataset, municipalities[start : start + cls.BATCH_SIZE]
                    )
            return dataset

    @classmethod
    def _copy_zip_source(
        cls, source: BinaryIO | Path, temporary_path: Path, source_name: str | None
    ) -> tuple[Path, str, str]:
        zip_name = source_name or Path(source).name
        if not zip_name.lower().endswith(".zip"):
            raise MunicipalityBoundaryImportError("ZIPファイルを指定してください。")

        zip_path = temporary_path / "source.zip"
        digest = hashlib.sha256()
        try:
            with zip_path.open("wb") as destination:
                if isinstance(source, Path):
                    source_file = source.open("rb")
                    close_source = True
                else:
                    source_file = source
                    close_source = False
                try:
                    while chunk := source_file.read(1024 * 1024):
                        digest.update(chunk)
                        destination.write(chunk)
                finally:
                    if close_source:
                        source_file.close()
        except OSError as error:
            raise MunicipalityBoundaryImportError(
                "ZIPファイルを読み込めませんでした。"
            ) from error

        if MunicipalitySoilRepository.boundary_zip_file_exists(digest.hexdigest()):
            raise MunicipalityBoundaryImportError("同じZIPはすでに取り込まれています。")
        return zip_path, zip_name, digest.hexdigest()

    @classmethod
    def _extract_zip_file(cls, zip_path: Path, extract_path: Path) -> None:
        try:
            with zipfile.ZipFile(zip_path) as zip_file:
                members = zip_file.infolist()
                if not members:
                    raise MunicipalityBoundaryImportError("ZIPが空です。")
                if (
                    sum(member.file_size for member in members)
                    > cls.MAX_UNCOMPRESSED_BYTES
                ):
                    raise MunicipalityBoundaryImportError(
                        "展開後のZIPサイズが上限を超えています。"
                    )
            ZipFileService.extract_zip_file(zip_path, extract_path)
        except zipfile.BadZipFile as error:
            raise MunicipalityBoundaryImportError("壊れたZIPファイルです。") from error
        except UnsafeZipPathError as error:
            raise MunicipalityBoundaryImportError(
                "ZIP内に展開できないパスが含まれています。"
            ) from error

    @staticmethod
    def _find_shape_path(extract_path: Path) -> Path:
        shape_files = list(extract_path.rglob("*.shp"))
        if len(shape_files) != 1:
            raise MunicipalityBoundaryImportError(
                "ZIPにはShapeファイルを1件だけ含めてください。"
            )
        shape_path = shape_files[0]
        missing = [
            suffix
            for suffix in (".dbf", ".shx", ".prj")
            if not shape_path.with_suffix(suffix).is_file()
        ]
        if missing:
            raise MunicipalityBoundaryImportError(
                f"Shapeファイルの必須構成ファイルがありません: {', '.join(missing)}"
            )
        return shape_path

    @staticmethod
    def _get_dbf_encoding(shape_path: Path) -> str:
        cpg_path = shape_path.with_suffix(".cpg")
        if not cpg_path.is_file():
            return "cp932"
        encoding_name = cpg_path.read_text(encoding="ascii", errors="ignore").strip()
        return encoding_name or "cp932"

    @classmethod
    def _validate_shape(
        cls, reader: shapefile.Reader, field_names: list[str], shape_path: Path
    ) -> None:
        if reader.shapeType not in {
            shapefile.POLYGON,
            shapefile.POLYGONM,
            shapefile.POLYGONZ,
        }:
            raise MunicipalityBoundaryImportError(
                "Polygon型のShapeファイルを指定してください。"
            )
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        missing = [
            field_name
            for field_name in cls.REQUIRED_FIELD_NAMES
            if field_name.upper() not in field_name_by_upper
        ]
        if missing:
            raise MunicipalityBoundaryImportError(
                f"必須属性がありません: {', '.join(missing)}"
            )
        crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8").upper()
        if "JGD_2011" not in crs and "JGD2011" not in crs:
            raise MunicipalityBoundaryImportError(
                "座標参照系がJGD_2011の行政区域データを指定してください。"
            )

    @classmethod
    def _build_municipalities(
        cls, reader: shapefile.Reader, field_names: list[str]
    ) -> tuple[list[dict], int]:
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        grouped_coordinates: dict[str, list] = defaultdict(list)
        municipality_names: dict[str, str] = {}
        feature_count = 0
        for row_number, shape_record in enumerate(reader.iterShapeRecords(), start=1):
            values = dict(zip(field_names, shape_record.record))
            try:
                municipality_code = cls._value(values, field_name_by_upper, "N03_007")
                if not municipality_code.isdigit() or len(municipality_code) != 5:
                    raise ValueError("行政区域コード")
                municipality_name = "".join(
                    str(
                        values.get(field_name_by_upper.get(field_name, "")) or ""
                    ).strip()
                    for field_name in ("N03_002", "N03_003", "N03_004", "N03_005")
                )
                if not municipality_name:
                    raise ValueError("市区町村名")
                geometry = shape_record.shape.__geo_interface__
                coordinates = cls._multipolygon_coordinates(geometry)
                if not coordinates:
                    raise ValueError("Polygon座標")
            except (TypeError, ValueError) as error:
                raise MunicipalityBoundaryImportError(
                    f"{row_number}件目の地物に不正な属性または座標があります。"
                ) from error

            grouped_coordinates[municipality_code].extend(coordinates)
            municipality_names[municipality_code] = municipality_name
            feature_count += 1

        municipalities = []
        for municipality_code, coordinates in grouped_coordinates.items():
            points = [
                point for polygon in coordinates for ring in polygon for point in ring
            ]
            municipalities.append(
                {
                    "prefecture_code": municipality_code[:2],
                    "municipality_code": municipality_code,
                    "name": municipality_names[municipality_code],
                    "coordinates": coordinates,
                    "min_lng": min(point[0] for point in points),
                    "min_lat": min(point[1] for point in points),
                    "max_lng": max(point[0] for point in points),
                    "max_lat": max(point[1] for point in points),
                }
            )
        return municipalities, feature_count

    @staticmethod
    def _multipolygon_coordinates(geometry: dict) -> list:
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon":
            return [coordinates]
        if geometry_type == "MultiPolygon":
            return coordinates
        raise ValueError("Polygon座標")

    @classmethod
    def _validate_national_coverage(cls, municipalities: list[dict]) -> None:
        included_codes = {
            municipality["prefecture_code"] for municipality in municipalities
        }
        if cls.NATIONAL_PREFECTURE_CODES - included_codes:
            raise MunicipalityBoundaryImportError(
                "全国版の行政区域Shape ZIPを指定してください。"
            )

    @staticmethod
    def _source_date_from_name(source_name: str) -> date:
        match = re.search(r"N03-(\d{8})", source_name)
        if not match:
            raise MunicipalityBoundaryImportError(
                "N03-YYYYMMDD形式の全国行政区域ZIPを指定してください。"
            )
        return date.fromisoformat(
            f"{match.group(1)[:4]}-{match.group(1)[4:6]}-{match.group(1)[6:]}"
        )

    @staticmethod
    def _value(
        values: dict, field_name_by_upper: dict[str, str], field_name: str
    ) -> str:
        value = values[field_name_by_upper[field_name.upper()]]
        result = str(value).strip()
        if not result:
            raise ValueError(field_name)
        return result
