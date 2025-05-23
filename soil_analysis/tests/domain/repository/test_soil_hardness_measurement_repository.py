from django.test import TestCase
from django.utils import timezone

from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.models import SoilHardnessMeasurement, Device, LandBlock


class TestSoilHardnessMeasurementRepository(TestCase):
    def setUp(self):
        """
        テストデータのセットアップ

        【実際の土壌硬度測定のプロセス】
        1. 圃場は通常3x3のマス目に分けられ、A1～C3の9ブロックとして捉えます。
        2. 各ブロックでは「5点法」を採用し、1つのブロック内の5箇所（四隅と中央）で測定を行い、それらの平均値をブロックの代表値とします。
        3. 各ブロックで測定された1回の計測を「メモリ」(set_memory)と呼びます。
        4. 1つのメモリで0～60cmまでの深度データを記録し、深度1cmごとに硬度値を記録します。
           （本テストでは簡略化のため60レコードではなく、1レコードのみ使用）
        5. 1つの圃場は最大9ブロックx各ブロック5点法=45箇所の測定が可能ですが、通常は5ブロックx5点法=25の測定（set_memory）が行われます。
           そのため、1つの圃場のset_memoryの最大値は25となります。

        【テストデータの構成】
        - 5つのブロック（A1, A3, B2, C1, C3）があり、各ブロックで5点法による測定を行います。
        - 各ブロックには5つのメモリが割り当てられ、合計25のメモリ（set_memory=1～25）となります。
          ブロック位置とメモリ番号の対応関係：
           - A1ブロック: メモリ1-5 （土地ブロック未割当）
           - A3ブロック: メモリ6-10 （土地ブロック未割当）
           - B2ブロック: メモリ11-15 （土地ブロック未割当）
           - C1ブロック: メモリ16-20 （テスト用ブロックAに割当済）
           - C3ブロック: メモリ21-25 （テスト用ブロックBに割当済）
        - これは実際の運用と同じ構成で、UI表示上も5つずつのブロックとしてグループ化され、
          5ブロック×5測定点=25のset_memoryが1つの圃場データとなります。
        - 実際の計測では1つのメモリに約60レコード（60cm分）のデータが含まれますが、
          テストの簡略化のため、各メモリには深度0, 15, 30, 45, 60cmの5レコードのみ設定しています。

        【データの内訳】
        - 全データ数: 300レコード（5メモリ×60深度）→テストでは25レコード（5メモリ×5深度）
        - 土地ブロック未割当: 180レコード（メモリ1,2,3の各60レコード）→テストでは15レコード
        - テスト用ブロックA割当: 60レコード（メモリ4の60レコード）→テストでは5レコード
        - テスト用ブロックB割当: 60レコード（メモリ5の60レコード）→テストでは5レコード
        """
        # テスト用デバイスの作成
        self.device = Device.objects.create(name="テスト用デバイス")

        # テスト用土地ブロックの作成
        self.land_block1 = LandBlock.objects.create(name="テスト用ブロックA")
        self.land_block2 = LandBlock.objects.create(name="テスト用ブロックB")

        # テスト用の計測データを作成
        self.base_datetime = timezone.now()
        self.measurements = []

        # メモリ1-5のデータを作成 (合計25個のデータ)
        for memory in range(1, 6):
            for depth in range(5):  # 各メモリに対して5つの深度
                measurement = SoilHardnessMeasurement.objects.create(
                    set_memory=memory,
                    set_datetime=self.base_datetime,
                    set_depth=30,
                    set_spring=1,
                    set_cone=1,
                    depth=depth * 5,  # 0, 5, 10, 15, 20
                    pressure=100 + depth,
                    folder="test_folder",
                    set_device=self.device,
                )
                self.measurements.append(measurement)

        # 一部のデータに土地ブロックを割り当て (メモリ4と5には土地ブロックを割り当て)
        for i in range(15, 25):  # メモリ4と5のデータ
            if i < 20:  # メモリ4のデータにはland_block1を割り当て
                self.measurements[i].land_block = self.land_block1
            else:  # メモリ5のデータにはland_block2を割り当て
                self.measurements[i].land_block = self.land_block2
            self.measurements[i].save()

    def test_get_measurements_by_memory_range(self):
        """
        get_measurements_by_memory_rangeメソッドのテスト

        このテストでは、指定したメモリ範囲内の計測データを正しく取得できることを確認します。
        特に以下の点を検証:
        1. 指定したメモリ範囲内のデータが正しく取得されるか
        2. 取得されたデータ数が期待通りか
        3. 取得されたデータが適切に並べられているか
        """
        # メモリ1から3の計測データを取得 (合計15個のデータになる)
        results = SoilHardnessMeasurementRepository.get_measurements_by_memory_range(
            1, 3
        )

        # 結果の検証
        self.assertEqual(len(results), 15)  # 3メモリ x 5深度 = 15データ
        self.assertEqual(results.first().set_memory, 1)  # 最初のデータのメモリが1
        self.assertEqual(results.last().set_memory, 3)  # 最後のデータのメモリが3

        # メモリの分布を確認
        memory_counts = {}
        for item in results:
            memory_counts[item.set_memory] = memory_counts.get(item.set_memory, 0) + 1

        # 各メモリごとに5つのデータが存在することを確認
        self.assertEqual(memory_counts, {1: 5, 2: 5, 3: 5})

        # 境界値のテスト - 1つだけのメモリデータを取得
        single_results = (
            SoilHardnessMeasurementRepository.get_measurements_by_memory_range(1, 1)
        )
        self.assertEqual(len(single_results), 5)  # 1メモリ x 5深度 = 5データ
        self.assertEqual(single_results.first().set_memory, 1)
        self.assertEqual(single_results.last().set_memory, 1)

    def test_group_measurements(self):
        """
        group_measurementsメソッドのテスト (クエリセットがNoneの場合)

        このテストでは、クエリセットを指定せずに土地ブロックが割り当てられていない
        計測データをメモリセットごとにグループ化できることを確認します。
        特に以下の点を検証:
        1. グループ化されたデータの数が期待通りか
        2. 各グループが正しいメモリ値を持つか
        3. 各グループが正しいカウント数を持つか
        4. 各グループが正しい日時値を持つか
        """
        # 土地ブロックが割り当てられていないデータをグループ化 (メモリ1,2,3のデータ = 15個)
        results = SoilHardnessMeasurementRepository.group_measurements()

        # 結果の検証
        self.assertEqual(len(results), 3)  # 割り当てられていないのはメモリ1,2,3の3つ

        # 各グループの内容を検証
        for i, group in enumerate(results, 1):
            self.assertEqual(
                group["set_memory"], i
            )  # メモリ番号が1,2,3と順番になっている
            self.assertEqual(group["cnt"], 5)  # 各メモリセットは5つの深度データを持つ
            self.assertEqual(group["set_datetime"], self.base_datetime)  # 日時が正しい

        # 集計されたデータの総数を確認
        total_records = sum(group["cnt"] for group in results)
        self.assertEqual(total_records, 15)  # land_block=Noneのデータは全部で15個

    def test_group_measurements_with_queryset(self):
        """
        group_measurementsメソッドのテスト (クエリセットを指定する場合)

        このテストでは、特定のクエリセットを指定してメモリセットごとに
        グループ化できることを確認します。
        特に以下の点を検証:
        1. 指定したクエリセットだけがグループ化対象になるか
        2. グループ化されたデータの数が期待通りか
        3. 各グループが正しいメモリ値と集計値を持つか
        4. グループの順序が正しく維持されるか
        """
        # メモリ1-3のデータのみを対象とする
        base_queryset = SoilHardnessMeasurement.objects.filter(set_memory__lte=3)
        results = SoilHardnessMeasurementRepository.group_measurements(base_queryset)

        # 結果の検証
        self.assertEqual(len(results), 3)  # 3つのメモリセットのみ

        # メモリ値が期待通りであることを確認
        memory_values = [group["set_memory"] for group in results]
        self.assertEqual(memory_values, [1, 2, 3])

        # 各グループのカウント数と日時を確認
        for group in results:
            self.assertEqual(group["cnt"], 5)  # 各メモリは5つのデータを持つ
            self.assertEqual(group["set_datetime"], self.base_datetime)

        # 異なるクエリセットでのテスト - 土地ブロックが割り当てられたデータのみ
        with_block_queryset = SoilHardnessMeasurement.objects.filter(
            land_block__isnull=False
        )
        with_block_results = SoilHardnessMeasurementRepository.group_measurements(
            with_block_queryset
        )

        self.assertEqual(len(with_block_results), 2)  # メモリ4と5の2つのグループ

        memory_values = [group["set_memory"] for group in with_block_results]
        self.assertEqual(memory_values, [4, 5])

        # 各グループのカウント数を確認
        for group in with_block_results:
            self.assertEqual(group["cnt"], 5)
