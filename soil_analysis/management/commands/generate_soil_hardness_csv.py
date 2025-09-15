import csv
import os
import random
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand

from soil_analysis.domain.valueobject.management.commands.generate_soil_hardness_csv import (
    SoilHardnessDevice,
    SoilHardnessCsvHeader,
    SoilHardnessCharacteristics,
)


class Command(BaseCommand):
    help = """
    土壌硬度計測器CSVファイルを生成するバッチ

    計測器制約:
    - 計測器は400メモリーまで保存可能
    - 1圃場あたり25メモリー消費のため、1日最大16圃場まで計測可能

    計測シナリオ:
    圃場は3x3の9ブロックに分かれるが、実際の計測は5ブロックのみ実施
    ┌────┬────┬────┐
    │ C3 │ B3 │ A3 │  → C3, A3を計測
    ├────┼────┼────┤
    │ C2 │ B2 │ A2 │  → B2のみ計測
    ├────┼────┼────┤
    │ C1 │ B1 │ A1 │  → C1, A1を計測
    └────┴────┴────┘

    各ブロックで5点法による5回の測定を実施
    1圃場あたり25メモリー（5ブロック × 5測定）を消費
    複数圃場を計測する場合、memoryは連番で増加し続ける
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--num_fields",
            type=int,
            default=1,
            help="生成する圃場数（最大16圃場）",
        )

    def handle(self, *args, **options):
        num_fields = min(options["num_fields"], 16)

        if options["num_fields"] > 16:
            self.stdout.write(
                self.style.WARNING(
                    f"指定された{options['num_fields']}圃場は計測器の制約により16圃場に制限されました"
                )
            )

        # 一時ディレクトリを作成
        output_path = Path(tempfile.mkdtemp(prefix="soil_hardness_"))

        # CSVファイル出力用のディレクトリ名を設定
        csv_output_path = output_path / "取り込みCSV"
        os.makedirs(csv_output_path, exist_ok=True)

        # 全圃場共通の測定日を生成（1日で全圃場を計測する前提）
        measurement_date = datetime.now() - timedelta(
            days=random.randint(1, 30),
            hours=random.randint(8, 17),  # 8時-17時の間で開始
            minutes=random.randint(0, 59),
        )
        date_str = measurement_date.strftime("%y.%m.%d %H:%M:%S")

        # 全圃場を通してmemoryを連番で管理
        global_memory_counter = 1
        total_files = 0
        for field_num in range(1, num_fields + 1):
            self.stdout.write(f"圃場 {field_num} のファイル生成中...")

            # 圃場ごとに異なるフォルダを作成（FIELD001など）
            field_dirname = f"FIELD{str(field_num).zfill(3)}"
            field_dir = os.path.join(csv_output_path, field_dirname)
            os.makedirs(field_dir, exist_ok=True)

            # 実際の計測では5ブロック（C1, C3, B2, A1, A3）のみを計測
            for block_idx in range(5):
                # 各ブロックで5回の測定
                for measurement in range(1, 6):
                    file_seq = str(global_memory_counter).zfill(4)
                    filename = f"{SoilHardnessDevice.DEVICE_NAME}_{file_seq}_N00000000_E000000000.csv"
                    filepath = os.path.join(field_dir, filename)
                    self._generate_csv_file(
                        filepath=filepath,
                        memory_no=global_memory_counter,
                        date_str=date_str,
                    )

                    global_memory_counter += 1
                    total_files += 1

        self.stdout.write(
            f"完了！{num_fields}圃場分、合計{total_files}ファイルを生成しました"
        )
        self.stdout.write(
            f"生成されたファイルは以下のディレクトリに保存されています: {output_path}"
        )
        self.stdout.write(
            "※このディレクトリは一時的なものです。必要に応じてファイルをコピーしてください。"
        )

        # 出力パスを返す（プログラムからの呼び出し用）
        return str(csv_output_path)

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
