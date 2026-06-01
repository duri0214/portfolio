import glob
import os

from soil_analysis.domain.repository.management.hardness_import_repository import (
    HardnessImportRepository,
)
from soil_analysis.domain.valueobject.management.hardness_csv_parser import (
    HardnessCSVParser,
)


class HardnessImportService:
    """
    土壌硬度データのインポートプロセスの調整を行うサービス
    """

    @classmethod
    def import_from_folder(cls, folder_path: str, logger=None) -> dict:
        """
        フォルダ内のCSVファイルから土壌硬度データを取り込む
        """
        if not folder_path or not os.path.exists(folder_path):
            raise ValueError(f"Folder path does not exist: {folder_path}")

        HardnessImportRepository.delete_all_errors()
        csv_files = glob.glob(os.path.join(folder_path, "**/*.csv"), recursive=True)

        total_created = 0
        file_results = []

        for csv_file in csv_files:
            try:
                rows = HardnessCSVParser.parse_csv(csv_file)
                created_count = 0
                for row in rows:
                    if HardnessImportRepository.save_measurement(row):
                        created_count += 1

                if created_count > 0:
                    total_created += created_count
                    file_results.append(
                        {"file": csv_file, "status": "success", "count": created_count}
                    )
            except Exception as e:
                parent_folder = os.path.basename(os.path.dirname(csv_file))
                file_name = os.path.basename(csv_file)
                HardnessImportRepository.create_error(
                    file=file_name, folder=parent_folder, message=str(e)
                )
                file_results.append(
                    {"file": csv_file, "status": "error", "message": str(e)}
                )

        return {"total_created": total_created, "file_results": file_results}
