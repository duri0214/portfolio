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
        parser.add_argument(
            "--field_pattern",
            type=str,
            choices=["standard", "dry", "wet", "compacted", "mixed"],
            default="standard",
            help="圃場の土壌パターン（standard:標準, dry:乾燥, wet:湿潤, compacted:締固め, mixed:混合）",
        )

    def handle(self, *args, **options):
        num_fields = options["num_fields"]
        field_pattern = options["field_pattern"]

        # 一時ディレクトリを作成
        output_path = Path(tempfile.mkdtemp(prefix="soil_hardness_"))

        # CSVファイル出力用のディレクトリ名を設定
        csv_output_path = output_path / "取り込みCSV"
        os.makedirs(csv_output_path, exist_ok=True)

        self.stdout.write(f"圃場パターン: {field_pattern}")

        total_files = 0
        for field_num in range(1, num_fields + 1):
            self.stdout.write(f"\n圃場 {field_num} のファイル生成中...")

            # 圃場ごとに異なるフォルダを作成（FIELD001など）
            field_dirname = f"FIELD{str(field_num).zfill(3)}"
            field_dir = os.path.join(csv_output_path, field_dirname)
            os.makedirs(field_dir, exist_ok=True)

            # 行（A, B, C）と列（1, 2, 3）の組み合わせで9ブロック
            file_counter = 1
            block_names = [f"{row}{col}" for row in "ABC" for col in "123"]

            for block_idx, block_name in enumerate(block_names):
                # ブロックごとの特性を設定
                block_characteristics = self._get_block_characteristics(
                    field_pattern, block_idx
                )

                # 各ブロックで複数回測定
                for measurement in range(1, 6):  # 5回の測定
                    # ファイル名生成（4桁のシーケンス番号）
                    file_seq = str(file_counter).zfill(4)
                    filename = f"{SoilHardnessDevice.DEVICE_NAME}_{file_seq}_N00000000_E000000000.csv"
                    filepath = os.path.join(field_dir, filename)

                    # CSVファイル生成
                    self._generate_csv_file(
                        filepath=filepath,
                        memory_no=file_counter,
                        characteristics=block_characteristics,
                        measurement_num=measurement,
                    )

                    file_counter += 1
                    total_files += 1

                    if file_counter % 10 == 0:
                        self.stdout.write(f"  {file_counter}ファイル生成完了...")

        self.stdout.write(
            self.style.SUCCESS(
                f"完了！{num_fields}圃場分、合計{total_files}ファイルを生成しました"
            )
        )

        self.stdout.write(
            f"生成されたファイルは以下のディレクトリに保存されています: {output_path}"
        )

        # 一時ディレクトリの注意書きを表示
        self.stdout.write(
            "※このディレクトリは一時的なものです。必要に応じてファイルをコピーしてください。"
        )

    def _get_block_characteristics(self, field_pattern, block_idx):
        """
        圃場のパターンに基づいて、ブロックごとの特性を決定する

        Args:
            field_pattern: 圃場パターン（standard, dry, wet, compacted, mixed）
            block_idx: ブロックのインデックス（0-8）

        Returns:
            dict: ブロックの特性情報
        """
        # 基本特性
        characteristics = {
            "base_pressure": 300,  # 基本圧力値
            "depth_factor": 10,  # 深度による増加係数
            "noise_range": (-150, 150),  # ノイズ範囲
            "hard_layer": None,  # 硬盤層の位置（cmの範囲）
            "hard_layer_strength": 0,  # 硬盤層の強さ係数
        }

        # 圃場パターンに応じた調整
        if field_pattern == "dry":
            characteristics["base_pressure"] = 400
            characteristics["depth_factor"] = 15
            characteristics["noise_range"] = (-100, 100)

        elif field_pattern == "wet":
            characteristics["base_pressure"] = 200
            characteristics["depth_factor"] = 5
            characteristics["noise_range"] = (-200, 100)

        elif field_pattern == "compacted":
            characteristics["base_pressure"] = 350
            characteristics["hard_layer"] = (15, 30)
            characteristics["hard_layer_strength"] = 300
            characteristics["depth_factor"] = 12

        elif field_pattern == "mixed":
            # 混合パターンでは、ブロックごとに異なる特性を割り当て
            patterns = ["standard", "dry", "wet", "compacted"]
            sub_pattern = patterns[block_idx % len(patterns)]
            return self._get_block_characteristics(sub_pattern, 0)

        # ブロックの位置に基づいた変動要素を追加
        row = block_idx // 3  # 0, 1, 2 (A, B, C)
        col = block_idx % 3  # 0, 1, 2 (1, 2, 3)

        # 圃場の端（row=0,2またはcol=0,2）では圧力が異なる傾向
        if row == 0 or row == 2 or col == 0 or col == 2:
            characteristics["base_pressure"] += random.randint(-50, 50)

        # 硬盤層の有無と深さをランダムに変化
        if random.random() < 0.3 and not characteristics["hard_layer"]:
            characteristics["hard_layer"] = (
                random.randint(10, 20),
                random.randint(25, 40),
            )
            characteristics["hard_layer_strength"] = random.randint(100, 400)

        return characteristics

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
            characteristics: ブロックの特性情報
            measurement_num: 測定回数（同一ブロック内での繰り返し番号）
        """
        # 特性が指定されていない場合のデフォルト値
        if characteristics is None:
            characteristics = {
                "base_pressure": 300,
                "depth_factor": 10,
                "noise_range": (-200, 200),
                "hard_layer": None,
                "hard_layer_strength": 0,
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

                # 硬盤層の影響を追加
                if (
                    characteristics["hard_layer"]
                    and characteristics["hard_layer"][0]
                    <= depth
                    <= characteristics["hard_layer"][1]
                ):
                    # 硬盤層内では急激に圧力が上昇
                    hard_layer_effect = characteristics["hard_layer_strength"]
                    hard_layer_position = (depth - characteristics["hard_layer"][0]) / (
                        characteristics["hard_layer"][1]
                        - characteristics["hard_layer"][0]
                    )
                    # 硬盤層の中央付近で最大値
                    hard_layer_multiplier = 1 - abs(hard_layer_position - 0.5) * 2
                    base_pressure += hard_layer_effect * hard_layer_multiplier

                # ランダム変動
                noise_min, noise_max = characteristics["noise_range"]
                random_variation = random.randint(noise_min, noise_max)

                # 前回値との連続性を考慮
                if depth > 1:
                    # 急激な変化を抑制
                    pressure_change_limit = 100  # 最大変化量
                    raw_pressure = base_pressure + random_variation
                    pressure_change = raw_pressure - prev_pressure

                    if abs(pressure_change) > pressure_change_limit:
                        # 変化量を制限
                        clamped_change = (
                            pressure_change_limit
                            if pressure_change > 0
                            else -pressure_change_limit
                        )
                        pressure = prev_pressure + clamped_change
                    else:
                        pressure = raw_pressure
                else:
                    pressure = base_pressure + random_variation

                # 最終的な圧力値: 範囲内に収める
                pressure = max(100, min(2500, pressure))
                prev_pressure = pressure  # 次回の連続性のために保存

                # データ行の書き込み
                writer.writerow([depth, int(pressure), date_str, 0, 0])
