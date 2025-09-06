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
                block_characteristics = self._get_simple_characteristics()

                # 各ブロックで5回の測定
                for measurement in range(1, 6):
                    file_seq = str(file_counter).zfill(4)
                    filename = f"{SoilHardnessDevice.DEVICE_NAME}_{file_seq}_N00000000_E000000000.csv"
                    filepath = os.path.join(field_dir, filename)
                    self._generate_csv_file(
                        filepath=filepath,
                        memory_no=file_counter,
                        characteristics=block_characteristics,
                        measurement_num=measurement,
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
    def _get_simple_characteristics():
        """
        シンプルな土壌特性を生成する

        Returns:
            dict: 土壌特性情報
        """
        # シンプルな特性
        return {
            "base_pressure": random.randint(232, 350),  # 初期圧力値（232～350）
            "depth_factor": random.randint(8, 15),  # 深度による増加係数
            "noise_range": (-100, 100),  # ばらつき範囲
        }

    @staticmethod
    def _generate_csv_file(
        filepath,
        memory_no,
        characteristics=None,
        measurement_num=1,
    ):
        """
        CSVファイルを生成する

        Args:
            filepath: 出力ファイルパス
            memory_no: メモリ番号
            characteristics: 土壌特性情報
            measurement_num: 測定回数（同一ブロック内での繰り返し番号）
        """
        # 特性が指定されていない場合のデフォルト値
        if characteristics is None:
            characteristics = {
                "base_pressure": 250,
                "depth_factor": 10,
                "noise_range": (-100, 100),
            }

        # 現在時刻からCSV用の日時形式に変換（測定日はランダム過去日）
        now = datetime.now() - timedelta(
            days=random.randint(1, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # 同一ブロック内での測定は時間差をつける
        now = now + timedelta(minutes=measurement_num * 2)  # 2分間隔で測定と仮定
        date_str = now.strftime("%y.%m.%d %H:%M:%S")

        # CSVデータの作成
        with open(filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # ヘッダー部分をValueObjectを使用して生成
            header_rows = SoilHardnessCsvHeader.create_header_rows(
                memory_no=memory_no,
                date_str=date_str,
            )

            # すべてのヘッダー行を書き込み
            for row in header_rows:
                writer.writerow(row)

            # 測定値の連続性を維持するための前回値
            prev_pressure = characteristics["base_pressure"]

            # 深度に応じて土壌圧力データを生成
            for depth in range(1, SoilHardnessDevice.MAX_DEPTH + 1):
                # 基本圧力: 特性に基づいて計算
                base_pressure = characteristics["base_pressure"] + (
                    depth * characteristics["depth_factor"]
                )

                # ランダム変動
                noise_min, noise_max = characteristics["noise_range"]
                random_variation = random.randint(noise_min, noise_max)

                # ランダムな変動を追加
                noise_min, noise_max = characteristics["noise_range"]
                random_variation = random.randint(noise_min, noise_max)

                # 前回値との連続性を考慮（急激な変化を抑制）
                if depth > 1:
                    max_change = 100  # 最大変化量
                    raw_pressure = base_pressure + random_variation
                    change = raw_pressure - prev_pressure

                    if abs(change) > max_change:
                        # 変化量を制限
                        pressure = prev_pressure + (
                            max_change if change > 0 else -max_change
                        )
                    else:
                        pressure = raw_pressure
                else:
                    pressure = base_pressure + random_variation

                # 最終的な圧力値: 232～3000の範囲に収める
                pressure = max(232, min(3000, pressure))
                prev_pressure = pressure  # 次回の連続性のために保存

                # データ行の書き込み
                writer.writerow([depth, int(pressure), date_str, 0, 0])
