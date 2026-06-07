import argparse
import csv
import os
import random
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import DatabaseError

from soil_analysis.domain.repository.device import DeviceRepository
from soil_analysis.domain.valueobject.management.commands.hardness_generate_dummy_csv import (
    SoilHardnessDevice,
    SoilHardnessCsvHeader,
    SoilHardnessCharacteristics,
)


class Command(BaseCommand):
    """
    土壌硬度計測器CSVファイルを生成するバッチ

    計測器制約:
    - 計測器は SoilHardnessDevice.DEFAULT_MAX_MEMORY メモリーまで保存可能
    - 1圃場あたり (BLOCKS_PER_FIELD * POINTS_PER_BLOCK) メモリー消費のため、最大圃場数はこれに基づき計算される

    計測シナリオ:
    圃場は3x3の9ブロックに分かれるが、実際の計測は BLOCKS_PER_FIELD ブロックのみ実施
    ┌────┬────┬────┐
    │ C3 │ B3 │ A3 │  → C3, A3を計測
    ├────┼────┼────┤
    │ C2 │ B2 │ A2 │  → B2のみ計測
    ├────┼────┼────┤
    │ C1 │ B1 │ A1 │  → C1, A1を計測
    └────┴────┴────┘

    各ブロックで POINTS_PER_BLOCK 点法による測定を実施
    複数圃場を計測する場合、memoryは連番で増加し続ける
    """

    BLOCKS_PER_FIELD = 5
    POINTS_PER_BLOCK = 5

    help = "土壌硬度計測器CSVファイルを生成します"
    # 詳細な説明を description に持たせる（RawDescriptionHelpFormatter で改行を維持）
    description = """
土壌硬度計測器CSVファイルを生成するバッチ

計測器制約:
- 計測器は SoilHardnessDevice.DEFAULT_MAX_MEMORY メモリーまで保存可能
- 1圃場あたり (BLOCKS_PER_FIELD * POINTS_PER_BLOCK) メモリー消費のため、最大圃場数はこれに基づき計算される

計測シナリオ:
圃場は3x3の9ブロックに分かれるが、実際の計測は BLOCKS_PER_FIELD ブロックのみ実施
┌────┬────┬────┐
│ C3 │ B3 │ A3 │  → C3, A3を計測
├────┼────┼────┤
│ C2 │ B2 │ A2 │  → B2のみ計測
├────┼────┼────┤
│ C1 │ B1 │ A1 │  → C1, A1を計測
└────┴────┴────┘

各ブロックで POINTS_PER_BLOCK 点法による測定を実施
複数圃場を計測する場合、memoryは連番で増加し続ける
"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--num_fields",
            type=int,
            default=1,
            help="生成する圃場数（最大16圃場）",
        )
        parser.add_argument(
            "--dataset_count",
            type=int,
            default=1,
            help="生成するアップロード用データセット数（最大2セット）",
        )

    def handle(self, *args, **options):
        num_fields = max(1, min(options["num_fields"], 16))
        dataset_count = max(1, min(options["dataset_count"], 2))

        if options["num_fields"] > 16:
            self.stdout.write(
                self.style.WARNING(
                    f"指定された{options['num_fields']}圃場は計測器の制約により16圃場に制限されました"
                )
            )
        if options["dataset_count"] > 2:
            self.stdout.write(
                self.style.WARNING(
                    f"指定された{options['dataset_count']}セットは検証用途の制約により2セットに制限されました"
                )
            )

        # 一時ディレクトリを作成
        output_path = Path(tempfile.mkdtemp(prefix="soil_hardness_"))

        # ブラウザからはこのフォルダをZIP化して返す。中に投入用ZIPを複数格納する。
        download_output_path = output_path / "hardness_samples"
        os.makedirs(download_output_path, exist_ok=True)

        total_files = 0
        readme_lines = [
            "土壌硬度 連続アップロード検証用データ",
            "",
            "hardness_upload_01.zip、hardness_upload_02.zip の順に soil:hardness_upload へ投入してください。",
            "各ZIPは測定日時・メモリ番号・フォルダ名が重複しないように生成されています。",
            "同じZIPを再投入すると、取り込み済みデータのエラー確認に使えます。",
            "",
        ]

        for dataset_index in range(1, dataset_count + 1):
            dataset_dir = output_path / f"hardness_upload_{dataset_index:02d}"
            os.makedirs(dataset_dir, exist_ok=True)
            total_files += self._generate_dataset(
                dataset_dir=dataset_dir,
                dataset_index=dataset_index,
                num_fields=num_fields,
            )

            zip_path = download_output_path / f"hardness_upload_{dataset_index:02d}.zip"
            self._zip_folder(dataset_dir, zip_path)
            readme_lines.append(
                f"- hardness_upload_{dataset_index:02d}.zip: {num_fields}圃場分"
            )

        (download_output_path / "README.txt").write_text(
            "\n".join(readme_lines), encoding="utf-8"
        )

        self.stdout.write(
            f"完了！{dataset_count}セット、各{num_fields}圃場分、合計{total_files}ファイルを生成しました"
        )
        self.stdout.write(
            f"生成されたファイルは以下のディレクトリに保存されています: {download_output_path}"
        )
        self.stdout.write(
            "※このディレクトリは一時的なものです。必要に応じてファイルをコピーしてください。"
        )

        # 出力パスを返す（プログラムからの呼び出し用）
        return str(download_output_path)

    @classmethod
    def _generate_dataset(
        cls, dataset_dir: Path, dataset_index: int, num_fields: int
    ) -> int:
        measurement_date = datetime(2026, 6, dataset_index, 9, 0, 0)
        date_str = measurement_date.strftime("%y.%m.%d %H:%M:%S")
        global_memory_counter = ((dataset_index - 1) * 200) + 1
        total_files = 0

        for field_num in range(1, num_fields + 1):
            field_dirname = f"FIELD{field_num:03d}_STAGE{dataset_index:02d}"
            field_dir = dataset_dir / field_dirname
            os.makedirs(field_dir, exist_ok=True)

            # 実際の計測では5ブロック（C1, C3, B2, A1, A3）のみを計測
            for _ in range(5):
                for _ in range(1, 6):
                    file_seq = str(global_memory_counter).zfill(4)
                    filename = f"{SoilHardnessDevice.DEVICE_NAME}_{file_seq}_N00000000_E000000000.csv"
                    filepath = field_dir / filename
                    random.seed(
                        (dataset_index * 1000) + (field_num * 100) + total_files
                    )
                    cls._generate_csv_file(
                        filepath=filepath,
                        memory_no=global_memory_counter,
                        date_str=date_str,
                    )

                    global_memory_counter += 1
                    total_files += 1

        return total_files

    @staticmethod
    def _zip_folder(source_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(source_dir)
                    zip_file.write(file_path, arc_name)

    @staticmethod
    def _generate_csv_file(filepath, memory_no, date_str):
        """
        CSVファイルを生成する

        Args:
            filepath: 出力ファイルパス
            memory_no: メモリ番号
            date_str: 測定日時文字列（全圃場で統一）
        """
        # 土壌特性は毎回ランダム値で生成
        characteristics = SoilHardnessCharacteristics()

        # CSVデータの作成
        with open(filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # ヘッダー部分をValueObjectを使用して生成
            header_rows = SoilHardnessCsvHeader.create_header_rows(
                memory_no=memory_no, date_str=date_str
            )
            for row in header_rows:
                writer.writerow(row)

            # 深度に応じて土壌圧力データを生成
            for depth in range(1, SoilHardnessDevice.MAX_DEPTH + 1):
                pressure = characteristics.calculate_pressure(depth)
                writer.writerow([depth, int(pressure), date_str, 0, 0])
