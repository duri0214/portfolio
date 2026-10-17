"""Shape ZIP取込ジョブを、ブラウザから呼ぶ短いステップへ分割する。"""

from __future__ import annotations

import hashlib
import shutil
from datetime import timedelta
from pathlib import Path

import shapefile
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from soil_analysis.domain.service.municipality_boundary_import import (
    MunicipalityBoundaryImportError,
    MunicipalityBoundaryImportService,
)
from soil_analysis.domain.service.soil_map_import import (
    SoilMapImportError,
    SoilMapImportService,
)
from soil_analysis.models import (
    MunicipalityBoundary,
    MunicipalityBoundaryDataset,
    ShapeImportJob,
    SoilMapDataset,
    SoilMapPolygon,
)


class ShapeImportJobError(Exception):
    """利用者へ表示できるShape取込ジョブのエラー。"""


class ShapeImportJobService:
    """保存済みZIPを一ステップずつ検証・取込・有効化する。"""

    BATCH_SIZE = 100
    PROCESSING_TIMEOUT = timedelta(minutes=10)

    @classmethod
    def create_job(cls, dataset_type: str, uploaded_file) -> ShapeImportJob:
        """アップロードZIPを保存し、重複を判定して取込ジョブを作成する。"""
        digest = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
        uploaded_file.seek(0)
        source_sha256 = digest.hexdigest()
        if (
            ShapeImportJob.objects.filter(source_sha256=source_sha256).exists()
            or SoilMapDataset.objects.filter(source_sha256=source_sha256).exists()
            or MunicipalityBoundaryDataset.objects.filter(
                source_sha256=source_sha256
            ).exists()
        ):
            raise ShapeImportJobError("同じZIPはすでに取り込み済み、または取込中です。")
        return ShapeImportJob.objects.create(
            dataset_type=dataset_type,
            source_file=uploaded_file,
            source_file_name=uploaded_file.name,
            source_sha256=source_sha256,
        )

    @classmethod
    def process_next_step(cls, job_id) -> ShapeImportJob:
        """ジョブの次の処理単位を実行し、進捗を保存して返す。"""
        job = cls._acquire(job_id)
        if job is None:
            return ShapeImportJob.objects.get(pk=job_id)

        try:
            if job.phase == ShapeImportJob.Phase.PREPARE:
                cls._prepare(job)
            elif job.phase == ShapeImportJob.Phase.IMPORT:
                cls._import_records(job)
            elif job.phase == ShapeImportJob.Phase.FINALIZE:
                cls._finalize(job)
            else:
                raise ShapeImportJobError("取込ジョブの処理段階が不正です。")
        except (
            ShapeImportJobError,
            SoilMapImportError,
            MunicipalityBoundaryImportError,
            OSError,
        ) as error:
            cls._mark_failed(job.pk, str(error))
        except Exception:
            cls._mark_failed(job.pk, "取込中に予期しないエラーが発生しました。")
        finally:
            ShapeImportJob.objects.filter(pk=job.pk).update(
                is_processing=False,
                processing_started_at=None,
                updated_at=timezone.now(),
            )
        return ShapeImportJob.objects.get(pk=job.pk)

    @classmethod
    def _acquire(cls, job_id) -> ShapeImportJob | None:
        now = timezone.now()
        updated_count = (
            ShapeImportJob.objects.filter(pk=job_id)
            .exclude(status=ShapeImportJob.Status.COMPLETED)
            .filter(
                Q(is_processing=False)
                | Q(processing_started_at__lt=now - cls.PROCESSING_TIMEOUT)
            )
            .update(
                is_processing=True,
                processing_started_at=now,
                status=ShapeImportJob.Status.RUNNING,
                error_message="",
                updated_at=now,
            )
        )
        if updated_count == 0:
            return None
        return ShapeImportJob.objects.get(pk=job_id)

    @classmethod
    def _prepare(cls, job: ShapeImportJob) -> None:
        work_path = cls._work_path(job)
        if work_path.exists():
            shutil.rmtree(work_path)
        work_path.mkdir(parents=True)

        zip_path = Path(job.source_file.path)
        if job.dataset_type == ShapeImportJob.DatasetType.SOIL_MAP:
            SoilMapImportService._extract_zip_file(zip_path, work_path)
            shape_path = SoilMapImportService._find_shape_path(work_path)
            validator = SoilMapImportService
        else:
            MunicipalityBoundaryImportService._extract_zip_file(zip_path, work_path)
            shape_path = MunicipalityBoundaryImportService._find_shape_path(work_path)
            validator = MunicipalityBoundaryImportService

        reader = shapefile.Reader(
            str(shape_path), encoding=validator._get_dbf_encoding(shape_path)
        )
        try:
            field_names = [field[0] for field in reader.fields[1:]]
            validator._validate_shape(reader, field_names, shape_path)
            total_record_count = len(reader)
        finally:
            reader.close()
        if total_record_count == 0:
            raise ShapeImportJobError("Shapeファイルにレコードがありません。")

        source_crs = shape_path.with_suffix(".prj").read_text(encoding="utf-8")
        with transaction.atomic():
            job = ShapeImportJob.objects.select_for_update().get(pk=job.pk)
            job.source_crs = source_crs
            job.total_record_count = total_record_count
            job.processed_record_count = 0
            job.excluded_record_count = 0
            if job.dataset_type == ShapeImportJob.DatasetType.SOIL_MAP:
                if job.soil_dataset_id is None:
                    job.soil_dataset = SoilMapDataset.objects.create(
                        source_file_name=job.source_file_name,
                        source_sha256=job.source_sha256,
                        source_crs=source_crs,
                        feature_count=0,
                        excluded_feature_count=0,
                        is_active=False,
                        imported_at=timezone.now(),
                    )
            elif job.boundary_dataset_id is None:
                job.boundary_dataset = MunicipalityBoundaryDataset.objects.create(
                    source_file_name=job.source_file_name,
                    source_sha256=job.source_sha256,
                    source_crs=source_crs,
                    source_date=MunicipalityBoundaryImportService._source_date_from_name(
                        job.source_file_name
                    ),
                    feature_count=0,
                    municipality_count=0,
                    is_active=False,
                    imported_at=timezone.now(),
                )
            job.phase = ShapeImportJob.Phase.IMPORT
            job.status = ShapeImportJob.Status.RUNNING
            job.save()

    @classmethod
    def _import_records(cls, job: ShapeImportJob) -> None:
        shape_path, validator = cls._shape_path_and_validator(job)
        reader = shapefile.Reader(
            str(shape_path), encoding=validator._get_dbf_encoding(shape_path)
        )
        try:
            field_names = [field[0] for field in reader.fields[1:]]
            start = job.processed_record_count
            end = min(start + cls.BATCH_SIZE, job.total_record_count)
            records = [reader.shapeRecord(index) for index in range(start, end)]
        finally:
            reader.close()

        with transaction.atomic():
            if job.dataset_type == ShapeImportJob.DatasetType.SOIL_MAP:
                excluded_count = cls._import_soil_records(
                    job, field_names, records, start
                )
            else:
                excluded_count = cls._import_boundary_records(
                    job, field_names, records, start
                )
            job = ShapeImportJob.objects.select_for_update().get(pk=job.pk)
            job.processed_record_count = end
            job.excluded_record_count += excluded_count
            if end >= job.total_record_count:
                job.phase = ShapeImportJob.Phase.FINALIZE
            job.save()

    @classmethod
    def _import_soil_records(
        cls,
        job: ShapeImportJob,
        field_names: list[str],
        records: list,
        start: int,
    ) -> int:
        polygons = []
        excluded_count = 0
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        for offset, shape_record in enumerate(records, start=1):
            values = dict(zip(field_names, shape_record.record))
            try:
                prefecture_code = SoilMapImportService._value(
                    values, field_name_by_upper, "PREF_JCD"
                )
                if not prefecture_code.isdigit() or not 1 <= int(prefecture_code) <= 47:
                    raise ValueError("都道府県コード")
                points = [
                    [float(lng), float(lat)]
                    for lng, lat, *_ in shape_record.shape.points
                ]
                if len(points) < 4:
                    raise ValueError("Polygon座標")
                attribute_names = ("SG_CD", "SSbG_CD", "SSerGrCD", "SoilName")
                attribute_values = [
                    str(values[field_name_by_upper[name.upper()]]).strip()
                    for name in attribute_names
                ]
                if not any(attribute_values):
                    excluded_count += 1
                    continue
                if not all(attribute_values):
                    raise ValueError("土壌図属性")
                part_starts = list(shape_record.shape.parts) + [len(points)]
                polygons.append(
                    {
                        "prefecture_code": f"{int(prefecture_code):02d}",
                        "soil_group_code": SoilMapImportService._value(
                            values, field_name_by_upper, "SG_CD"
                        ),
                        "soil_subgroup_code": SoilMapImportService._value(
                            values, field_name_by_upper, "SSBG_CD"
                        ),
                        "soil_series_code": SoilMapImportService._value(
                            values, field_name_by_upper, "SSERGRCD"
                        ),
                        "soil_name": SoilMapImportService._value(
                            values, field_name_by_upper, "SOILNAME"
                        ),
                        "coordinates": [
                            points[part_starts[index] : part_starts[index + 1]]
                            for index in range(len(part_starts) - 1)
                        ],
                        "min_lng": min(point[0] for point in points),
                        "min_lat": min(point[1] for point in points),
                        "max_lng": max(point[0] for point in points),
                        "max_lat": max(point[1] for point in points),
                    }
                )
            except (TypeError, ValueError) as error:
                raise ShapeImportJobError(
                    f"{start + offset}件目の属性または座標が不正です。"
                ) from error

        with transaction.atomic():
            SoilMapPolygon.objects.bulk_create(
                [
                    SoilMapPolygon(dataset=job.soil_dataset, **polygon)
                    for polygon in polygons
                ],
                batch_size=cls.BATCH_SIZE,
            )
        return excluded_count

    @classmethod
    def _import_boundary_records(
        cls,
        job: ShapeImportJob,
        field_names: list[str],
        records: list,
        start: int,
    ) -> int:
        field_name_by_upper = {
            field_name.upper(): field_name for field_name in field_names
        }
        features: dict[str, dict] = {}
        for offset, shape_record in enumerate(records, start=1):
            values = dict(zip(field_names, shape_record.record))
            try:
                municipality_code = MunicipalityBoundaryImportService._value(
                    values, field_name_by_upper, "N03_007"
                )
                if not municipality_code.isdigit() or len(municipality_code) != 5:
                    raise ValueError("市区町村コード")
                name = "".join(
                    str(values.get(field_name_by_upper.get(name, "")) or "").strip()
                    for name in ("N03_002", "N03_003", "N03_004", "N03_005")
                )
                if not name:
                    raise ValueError("市区町村名")
                coordinates = (
                    MunicipalityBoundaryImportService._multipolygon_coordinates(
                        shape_record.shape.__geo_interface__
                    )
                )
                points = [
                    point
                    for polygon in coordinates
                    for ring in polygon
                    for point in ring
                ]
                if not points:
                    raise ValueError("Polygon座標")
            except (TypeError, ValueError) as error:
                raise ShapeImportJobError(
                    f"{start + offset}件目の属性または座標が不正です。"
                ) from error

            feature = features.setdefault(
                municipality_code,
                {
                    "prefecture_code": municipality_code[:2],
                    "municipality_code": municipality_code,
                    "name": name,
                    "coordinates": [],
                    "min_lng": min(point[0] for point in points),
                    "min_lat": min(point[1] for point in points),
                    "max_lng": max(point[0] for point in points),
                    "max_lat": max(point[1] for point in points),
                },
            )
            feature["coordinates"].extend(coordinates)
            feature["min_lng"] = min(
                feature["min_lng"], min(point[0] for point in points)
            )
            feature["min_lat"] = min(
                feature["min_lat"], min(point[1] for point in points)
            )
            feature["max_lng"] = max(
                feature["max_lng"], max(point[0] for point in points)
            )
            feature["max_lat"] = max(
                feature["max_lat"], max(point[1] for point in points)
            )

        with transaction.atomic():
            existing = {
                boundary.municipality_code: boundary
                for boundary in MunicipalityBoundary.objects.select_for_update().filter(
                    dataset=job.boundary_dataset,
                    municipality_code__in=features,
                )
            }
            new_boundaries = []
            updated_boundaries = []
            for code, feature in features.items():
                boundary = existing.get(code)
                if boundary is None:
                    new_boundaries.append(
                        MunicipalityBoundary(dataset=job.boundary_dataset, **feature)
                    )
                    continue
                boundary.coordinates.extend(feature["coordinates"])
                boundary.min_lng = min(boundary.min_lng, feature["min_lng"])
                boundary.min_lat = min(boundary.min_lat, feature["min_lat"])
                boundary.max_lng = max(boundary.max_lng, feature["max_lng"])
                boundary.max_lat = max(boundary.max_lat, feature["max_lat"])
                updated_boundaries.append(boundary)
            MunicipalityBoundary.objects.bulk_create(
                new_boundaries, batch_size=cls.BATCH_SIZE
            )
            MunicipalityBoundary.objects.bulk_update(
                updated_boundaries,
                ["coordinates", "min_lng", "min_lat", "max_lng", "max_lat"],
                batch_size=cls.BATCH_SIZE,
            )
        return 0

    @classmethod
    def _finalize(cls, job: ShapeImportJob) -> None:
        if job.dataset_type == ShapeImportJob.DatasetType.SOIL_MAP:
            cls._finalize_soil_dataset(job)
        else:
            cls._finalize_boundary_dataset(job)
        ShapeImportJob.objects.filter(pk=job.pk).update(
            status=ShapeImportJob.Status.COMPLETED,
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )

    @classmethod
    def _finalize_soil_dataset(cls, job: ShapeImportJob) -> None:
        dataset = job.soil_dataset
        if dataset is None:
            raise ShapeImportJobError("土壌図データ版を作成できませんでした。")
        feature_count = SoilMapPolygon.objects.filter(dataset=dataset).count()
        if feature_count == 0:
            raise ShapeImportJobError("ShapeファイルにPolygonがありません。")
        codes = set(
            SoilMapPolygon.objects.filter(dataset=dataset).values_list(
                "prefecture_code", flat=True
            )
        )
        missing = sorted(SoilMapImportService.NATIONAL_PREFECTURE_CODES - codes)
        if missing:
            raise ShapeImportJobError(
                "全国版のShape ZIPを指定してください。"
                f"不足している都道府県コード: {', '.join(missing)}"
            )
        with transaction.atomic():
            SoilMapDataset.objects.filter(is_active=True).exclude(pk=dataset.pk).update(
                is_active=False
            )
            SoilMapDataset.objects.filter(pk=dataset.pk).update(
                feature_count=feature_count,
                excluded_feature_count=job.excluded_record_count,
                is_active=True,
            )

    @classmethod
    def _finalize_boundary_dataset(cls, job: ShapeImportJob) -> None:
        dataset = job.boundary_dataset
        if dataset is None:
            raise ShapeImportJobError("市区町村境界データ版を作成できませんでした。")
        codes = set(
            MunicipalityBoundary.objects.filter(dataset=dataset).values_list(
                "prefecture_code", flat=True
            )
        )
        if MunicipalityBoundaryImportService.NATIONAL_PREFECTURE_CODES - codes:
            raise ShapeImportJobError(
                "全国版の市区町村境界Shape ZIPを指定してください。"
            )
        with transaction.atomic():
            MunicipalityBoundaryDataset.objects.filter(is_active=True).exclude(
                pk=dataset.pk
            ).update(is_active=False)
            MunicipalityBoundaryDataset.objects.filter(pk=dataset.pk).update(
                feature_count=job.processed_record_count,
                municipality_count=MunicipalityBoundary.objects.filter(
                    dataset=dataset
                ).count(),
                is_active=True,
            )

    @classmethod
    def _shape_path_and_validator(cls, job: ShapeImportJob):
        work_path = cls._work_path(job)
        if not work_path.is_dir():
            raise ShapeImportJobError(
                "展開済みZIPが見つかりません。もう一度実行してください。"
            )
        if job.dataset_type == ShapeImportJob.DatasetType.SOIL_MAP:
            return (
                SoilMapImportService._find_shape_path(work_path),
                SoilMapImportService,
            )
        return (
            MunicipalityBoundaryImportService._find_shape_path(work_path),
            MunicipalityBoundaryImportService,
        )

    @staticmethod
    def _work_path(job: ShapeImportJob) -> Path:
        return (
            Path(settings.MEDIA_ROOT)
            / "soil_analysis"
            / "shape_import_jobs"
            / str(job.pk)
        )

    @staticmethod
    def _mark_failed(job_id, message: str) -> None:
        ShapeImportJob.objects.filter(pk=job_id).update(
            status=ShapeImportJob.Status.FAILED,
            error_message=message[:1000],
            updated_at=timezone.now(),
        )
