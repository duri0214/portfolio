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

# 圧力値の変化量の最大値（急激な変化を防ぐための制限値）
MAX_PRESSURE_DELTA = 100


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

            # 初期圧力値（表層の柔らかさ）
            base_pressure = characteristics.base_pressure

            # 深度に応じて土壌圧力データを生成
            for depth in range(1, SoilHardnessDevice.MAX_DEPTH + 1):
                # 数学関数式: P(d) = P₀ + k × (d/d_max)²
                # P₀: 基本圧力値, d: 深度, d_max: 最大深度, k: 最大増加圧力
                # 2次関数モデルにより深度の増加に対して加速度的に圧力が増加

                # 係数を調整して適切な曲線を作る
                depth_ratio = depth / SoilHardnessDevice.MAX_DEPTH  # 0～1の比率
                quadratic_factor = depth_ratio**2  # 2次関数的な増加

                # 深度60cmで最大になる曲線を作成
                max_pressure_increase = 2000  # 最大増加量
                depth_pressure = base_pressure + (
                    quadratic_factor * max_pressure_increase
                )

                # 自然な揺らぎを追加（常に正の値を加算）
                random_variation = random.randint(10, 50)

                # 圧力値を計算（前回値との連続性も考慮）
                calculated_pressure = int(depth_pressure) + random_variation

                # 前回値からの増加量が大きすぎる場合は制限する
                if depth > 1:
                    delta = calculated_pressure - last_depth_pressure

                    if delta > MAX_PRESSURE_DELTA:
                        pressure = last_depth_pressure + MAX_PRESSURE_DELTA
                    else:
                        pressure = calculated_pressure
                else:
                    pressure = calculated_pressure

                # 最終的な圧力値: 232～3000の範囲に収める
                pressure = max(232, min(3000, pressure))
                last_depth_pressure = pressure  # 次回の連続性のために保存

                # データ行の書き込み
                writer.writerow([depth, int(pressure), date_str, 0, 0])
