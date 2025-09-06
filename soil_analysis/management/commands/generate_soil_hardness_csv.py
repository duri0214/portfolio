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
    help = "土壌硬度計測器CSVファイルを生成するバッチ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--num_fields",
            type=int,
            default=1,
            help="生成する圃場数",
        )

    def handle(self, *args, **options):
        num_fields = options["num_fields"]

        # 一時ディレクトリを作成
        output_path = Path(tempfile.mkdtemp(prefix="soil_hardness_"))

        # CSVファイル出力用のディレクトリ名を設定
        csv_output_path = output_path / "取り込みCSV"
        os.makedirs(csv_output_path, exist_ok=True)

        total_files = 0
        for field_num in range(1, num_fields + 1):
            self.stdout.write(f"圃場 {field_num} のファイル生成中...")

            # 圃場ごとに異なるフォルダを作成（FIELD001など）
            field_dirname = f"FIELD{str(field_num).zfill(3)}"
            field_dir = os.path.join(csv_output_path, field_dirname)
            os.makedirs(field_dir, exist_ok=True)

            # 行（A, B, C）と列（1, 2, 3）の組み合わせで9ブロック
            file_counter = 1
            for block_idx in range(9):
                # 各ブロックで5回の測定
                for measurement in range(1, 6):
                    file_seq = str(file_counter).zfill(4)
                    filename = f"{SoilHardnessDevice.DEVICE_NAME}_{file_seq}_N00000000_E000000000.csv"
                    filepath = os.path.join(field_dir, filename)
                    self._generate_csv_file(
                        filepath=filepath,
                        memory_no=file_counter,
                    )

                    file_counter += 1
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

    @staticmethod
    def _generate_csv_file(filepath, memory_no):
        """
        CSVファイルを生成する

        Args:
            filepath: 出力ファイルパス
            memory_no: メモリ番号
        """
        # 土壌特性は毎回ランダム値で生成
        characteristics = SoilHardnessCharacteristics()

        # 現在時刻からCSV用の日時形式に変換（測定日はランダム過去日）
        now = datetime.now() - timedelta(
            days=random.randint(1, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        date_str = now.strftime("%y.%m.%d %H:%M:%S")

        # CSVデータの作成
        with open(filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # ヘッダー部分をValueObjectを使用して生成
            header_rows = SoilHardnessCsvHeader.create_header_rows(
                memory_no=memory_no, date_str=date_str
            )

            # すべてのヘッダー行を書き込み
            for row in header_rows:
                writer.writerow(row)

            # 深度に応じて土壌圧力データを生成
            for depth in range(1, SoilHardnessDevice.MAX_DEPTH + 1):
                # ValueObjectの計算メソッドを使用
                pressure = characteristics.calculate_pressure_for_depth(depth=depth)

                # データ行の書き込み
                writer.writerow([depth, int(pressure), date_str, 0, 0])
