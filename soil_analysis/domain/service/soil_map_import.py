"""日本土壌インベントリーのShape ZIPを検証して保存するサービス。"""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

import shapefile
from django.db import transaction
from django.utils import timezone

from lib.zipfileservice import UnsafeZipPathError, ZipFileService
from soil_analysis.domain.repository.soil_map import SoilMapRepository
from soil_analysis.domain.service.soil_classification import normalize_soil_name
from soil_analysis.models import SoilMapDataset


class SoilMapImportError(Exception):
    """利用者に安全に伝えられる土壌図の検証・取込エラー。"""


class SoilMapImportService:
    """全国20万分の1土壌図のShape ZIPを、一つのデータ版として取り込む。"""

    REQUIRED_FIELD_NAMES = ("Pref_JCD", "SG_CD", "SSbG_CD", "SSerGrCD", "SoilName")
    NATIONAL_PREFECTURE_CODES = frozenset(f"{code:02d}" for code in range(1, 48))
    MAX_UNCOMPRESSED_BYTES = 1_500 * 1024 * 1024
    BATCH_SIZE = 500

    @classmethod
    def import_soil_map_from_zip(
        cls, source: BinaryIO | Path, source_name: str | None = None
    ) -> SoilMapDataset:
        """ZIPを検証し、すべて保存できた場合だけ有効版を切り替える。

        Args:
            source: アップロード済みファイル、またはローカルのZIPパス。
            source_name: 画面に残す元ファイル名。パス指定時は省略できる。

        Returns:
            SoilMapDataset: 新しく有効になったデータ版。

        Raises:
            SoilMapImportError: ZIPまたはShapeの契約を満たさない場合。
        """
        with tempfile.TemporaryDirectory(prefix="soil-map-") as temporary_directory:
            temporary_path = Path(temporary_directory)
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
                polygons, excluded_feature_count = cls._build_polygons(
                    reader, field_names
                )
            finally:
                reader.close()

            if not polygons:
                raise SoilMapImportError("ShapeファイルにPolygonがありません。")

            cls._validate_national_coverage(polygons)

            source_crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8")
            with transaction.atomic():
                SoilMapRepository.deactivate_active_datasets()
                dataset = SoilMapRepository.create_dataset(
                    source_file_name=zip_name,
                    source_sha256=digest,
                    source_crs=source_crs,
                    feature_count=len(polygons),
                    excluded_feature_count=excluded_feature_count,
                    is_active=True,
                    imported_at=timezone.now(),
                )
                for start in range(0, len(polygons), cls.BATCH_SIZE):
                    SoilMapRepository.bulk_create_polygons(
                        dataset, polygons[start : start + cls.BATCH_SIZE]
                    )
            return dataset

    @classmethod
    def _copy_zip_source(
        cls, source: BinaryIO | Path, temporary_path: Path, source_name: str | None
    ) -> tuple[Path, str, str]:
        zip_name = source_name or Path(source).name
        if not zip_name.lower().endswith(".zip"):
            raise SoilMapImportError("ZIPファイルを指定してください。")

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
            raise SoilMapImportError("ZIPファイルを読み込めませんでした。") from error

        if SoilMapRepository.zip_file_exists(digest.hexdigest()):
            raise SoilMapImportError("同じZIPはすでに取り込まれています。")
        return zip_path, zip_name, digest.hexdigest()

    @classmethod
    def _extract_zip_file(cls, zip_path: Path, extract_path: Path) -> None:
        try:
            with zipfile.ZipFile(zip_path) as zip_file:
                members = zip_file.infolist()
                if not members:
                    raise SoilMapImportError("ZIPが空です。")
                total_size = sum(member.file_size for member in members)
                if total_size > cls.MAX_UNCOMPRESSED_BYTES:
                    raise SoilMapImportError("展開後のZIPサイズが上限を超えています。")
            ZipFileService.extract_zip_file(zip_path, extract_path)
        except zipfile.BadZipFile as error:
            raise SoilMapImportError("壊れたZIPファイルです。") from error
        except UnsafeZipPathError as error:
            raise SoilMapImportError(
                "ZIP内に展開できないパスが含まれています。"
            ) from error

    @classmethod
    def _find_shape_path(cls, extract_path: Path) -> Path:
        shape_files = list(extract_path.rglob("*.shp"))
        if len(shape_files) != 1:
            raise SoilMapImportError("ZIPにはShapeファイルを1件だけ含めてください。")
        shape_path = shape_files[0]
        missing = [
            suffix
            for suffix in (".dbf", ".shx", ".prj")
            if not shape_path.with_suffix(suffix).is_file()
        ]
        if missing:
            raise SoilMapImportError(
                f"Shapeファイルの必須構成ファイルがありません: {', '.join(missing)}"
            )
        return shape_path

    @staticmethod
    def _get_dbf_encoding(shape_path: Path) -> str:
        """DBFの文字コードをCPGから判定し、未指定時はCP932を使う。

        日本土壌インベントリーのDBFには日本語の土壌名が入るため、pyshpの既定UTF-8
        のままではデコードできない配布物があります。CPGがない国内ShapeはCP932として
        読み込みます。
        """
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
            raise SoilMapImportError("Polygon型のShapeファイルを指定してください。")
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        missing = [
            field_name
            for field_name in cls.REQUIRED_FIELD_NAMES
            if field_name.upper() not in field_name_by_upper
        ]
        if missing:
            raise SoilMapImportError(f"必須属性がありません: {', '.join(missing)}")
        crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8").upper()
        if "JGD_2000" not in crs and "JGD2000" not in crs:
            raise SoilMapImportError(
                "座標参照系がJGD_2000のShapeファイルを指定してください。"
            )

    @classmethod
    def _build_polygons(
        cls, reader: shapefile.Reader, field_names: list[str]
    ) -> tuple[list[dict], int]:
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        polygons = []
        excluded_feature_count = 0
        for row_number, shape_record in enumerate(reader.iterShapeRecords(), start=1):
            values = dict(zip(field_names, shape_record.record))
            try:
                prefecture_code = cls._value(values, field_name_by_upper, "PREF_JCD")
                if not prefecture_code.isdigit() or not 1 <= int(prefecture_code) <= 47:
                    raise ValueError("都道府県コード")
                points = [
                    [float(lng), float(lat)]
                    for lng, lat, *_ in shape_record.shape.points
                ]
                if len(points) < 4:
                    raise ValueError("Polygon座標")
                attribute_field_names = ("SG_CD", "SSbG_CD", "SSerGrCD", "SoilName")
                soil_name = normalize_soil_name(values[field_name_by_upper["SOILNAME"]])
                attribute_values = [
                    str(values[field_name_by_upper[field_name.upper()]]).strip()
                    for field_name in attribute_field_names[:-1]
                ] + [soil_name]
                if not any(attribute_values):
                    excluded_feature_count += 1
                    continue
                if not all(attribute_values):
                    raise ValueError("土壌属性")
                part_starts = list(shape_record.shape.parts) + [len(points)]
                coordinates = [
                    points[part_starts[index] : part_starts[index + 1]]
                    for index in range(len(part_starts) - 1)
                ]
                polygons.append(
                    {
                        "prefecture_code": f"{int(prefecture_code):02d}",
                        "soil_group_code": cls._value(
                            values, field_name_by_upper, "SG_CD"
                        ),
                        "soil_subgroup_code": cls._value(
                            values, field_name_by_upper, "SSBG_CD"
                        ),
                        "soil_series_code": cls._value(
                            values, field_name_by_upper, "SSerGrCD"
                        ),
                        "soil_name": soil_name,
                        "coordinates": coordinates,
                        "min_lng": min(point[0] for point in points),
                        "min_lat": min(point[1] for point in points),
                        "max_lng": max(point[0] for point in points),
                        "max_lat": max(point[1] for point in points),
                    }
                )
            except (TypeError, ValueError) as error:
                raise SoilMapImportError(
                    f"{row_number}件目の地物に不正な属性または座標があります。"
                ) from error
        return polygons, excluded_feature_count

    @classmethod
    def _validate_national_coverage(cls, polygons: list[dict]) -> None:
        """47都道府県を含む全国版だけを受け入れ、県別版との重複登録を防ぐ。"""
        included_codes = {polygon["prefecture_code"] for polygon in polygons}
        missing_codes = sorted(cls.NATIONAL_PREFECTURE_CODES - included_codes)
        if missing_codes:
            raise SoilMapImportError(
                "全国版のShape ZIPを指定してください。"
                f"不足している都道府県コード: {', '.join(missing_codes)}"
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
