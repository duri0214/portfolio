"""日本土壌インベントリーのShape ZIPを検証して保存するサービス。"""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import shapefile
from django.db import transaction
from django.utils import timezone

from soil_analysis.domain.repository.soil_map import SoilMapRepository
from soil_analysis.models import SoilMapDataset


class SoilMapImportError(Exception):
    """利用者に安全に伝えられる土壌図の検証・取込エラー。"""


class SoilMapImportService:
    """全国20万分の1土壌図のShape ZIPを、一つのデータ版として取り込む。"""

    REQUIRED_FIELD_NAMES = ("Pref_JCD", "SG_CD", "SSbG_CD", "SSerGrCD", "SoilName")
    MAX_UNCOMPRESSED_BYTES = 1_500 * 1024 * 1024
    BATCH_SIZE = 500

    @classmethod
    def import_archive(
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
            archive_path, archive_name, digest = cls._copy_source(
                source, temporary_path, source_name
            )
            extract_path = temporary_path / "extract"
            cls._extract_archive(archive_path, extract_path)
            shape_path = cls._find_shape_path(extract_path)
            reader = shapefile.Reader(str(shape_path))
            try:
                field_names = [field[0] for field in reader.fields[1:]]
                cls._validate_shape(reader, field_names, shape_path)
                polygons = cls._build_polygons(reader, field_names)
            finally:
                reader.close()

            if not polygons:
                raise SoilMapImportError("ShapeファイルにPolygonがありません。")

            source_crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8")
            with transaction.atomic():
                SoilMapRepository.deactivate_active_datasets()
                dataset = SoilMapRepository.create_dataset(
                    source_file_name=archive_name,
                    source_sha256=digest,
                    source_crs=source_crs,
                    feature_count=len(polygons),
                    is_active=True,
                    imported_at=timezone.now(),
                )
                for start in range(0, len(polygons), cls.BATCH_SIZE):
                    SoilMapRepository.bulk_create_polygons(
                        dataset, polygons[start : start + cls.BATCH_SIZE]
                    )
            return dataset

    @classmethod
    def _copy_source(
        cls, source: BinaryIO | Path, temporary_path: Path, source_name: str | None
    ) -> tuple[Path, str, str]:
        archive_name = source_name or Path(source).name
        if not archive_name.lower().endswith(".zip"):
            raise SoilMapImportError("ZIPファイルを指定してください。")

        archive_path = temporary_path / "source.zip"
        digest = hashlib.sha256()
        try:
            with archive_path.open("wb") as destination:
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

        if SoilMapRepository.archive_exists(digest.hexdigest()):
            raise SoilMapImportError("同じZIPはすでに取り込まれています。")
        return archive_path, archive_name, digest.hexdigest()

    @classmethod
    def _extract_archive(cls, archive_path: Path, extract_path: Path) -> None:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                if not members:
                    raise SoilMapImportError("ZIPが空です。")
                total_size = sum(member.file_size for member in members)
                if total_size > cls.MAX_UNCOMPRESSED_BYTES:
                    raise SoilMapImportError("展開後のZIPサイズが上限を超えています。")
                for member in members:
                    member_path = PurePosixPath(member.filename)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise SoilMapImportError(
                            "ZIP内に展開できないパスが含まれています。"
                        )
                archive.extractall(extract_path)
        except zipfile.BadZipFile as error:
            raise SoilMapImportError("壊れたZIPファイルです。") from error

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
    ) -> list[dict]:
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        polygons = []
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
                        "soil_name": cls._value(
                            values, field_name_by_upper, "SOILNAME"
                        ),
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
        return polygons

    @staticmethod
    def _value(
        values: dict, field_name_by_upper: dict[str, str], field_name: str
    ) -> str:
        value = values[field_name_by_upper[field_name.upper()]]
        result = str(value).strip()
        if not result:
            raise ValueError(field_name)
        return result
