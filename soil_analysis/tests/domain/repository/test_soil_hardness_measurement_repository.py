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
           ブロックは以下のように配置され、A1が右下（南東）、C3が左上（北西）に位置します：
           C3 B3 A3
           C2 B2 A2
           C1 B1 A1
        2. 各ブロックでは「5点法」を採用し、1つのブロック内の5箇所（四隅と中央）で測定を行い、それらの平均値をブロックの代表値とします。
        3. 各ブロックで測定された1回の計測を「メモリ」(set_memory)と呼びます。
        4. 1つのメモリで0～60cmまでの深度データを記録し、深度1cmごとに硬度値を記録します。
           （本テストでは簡略化のため60レコードではなく、1レコードのみ使用）
        5. 1つの圃場は最大9ブロックx各ブロック5点法=45箇所の測定が可能ですが、通常は5ブロックx5点法=25の測定（set_memory）が行われます。
           そのため、1つの圃場のset_memoryの最大値は25となります。

        【テストデータの構成】
        - 5つのブロック（A1, A3, B2, C1, C3）があり、各ブロックで5点法による測定を行います。
        - 各ブロックには5つのメモリが割り当てられ、合計25のメモリ（set_memory=1～25）となります。
        - 圃場における位置関係は以下の通りです：
           C3 B3 A3
           C2 B2 A2
           C1 B1 A1

        - Rパターンでの測定順序に従い、ブロック位置とメモリ番号の対応関係：
           - C1ブロック: メモリ1-5 （土地ブロック未割当）
           - C3ブロック: メモリ6-10 （土地ブロック未割当）
           - A3ブロック: メモリ11-15 （土地ブロック未割当）
           - B2ブロック: メモリ16-20 （テスト用ブロックAに割当済）
           - A1ブロック: メモリ21-25 （テスト用ブロックBに割当済）
        - これは実際の運用と同じ構成で、UI表示上も5つずつのブロックとしてグループ化され、
          5ブロック×5測定点=25のset_memoryが1つの圃場データとなります。
        - 実際の計測では1つのメモリに約60レコード（60cm分）のデータが含まれますが、
          テストの簡略化のため、各メモリには深度0, 15, 30, 45, 60cmの5レコードのみ設定しています。

        【データの内訳】
        - 全データ数: 25レコード（25メモリ×1深度）→実際の運用では1500レコード（25メモリ×60深度）
        - 土地ブロック未割当: 15レコード（C1, C3, A3ブロックのメモリ1-15）→実際の運用では900レコード
          - C1ブロック: メモリ1-5 → 5レコード（実際の運用では300レコード）
          - C3ブロック: メモリ6-10 → 5レコード（実際の運用では300レコード）
          - A3ブロック: メモリ11-15 → 5レコード（実際の運用では300レコード）
        - 土地ブロック割当済み: 10レコード（B2, A1ブロックのメモリ16-25）→実際の運用では600レコード
          - B2ブロック: メモリ16-20 → 5レコード（実際の運用では300レコード）
          - A1ブロック: メモリ21-25 → 5レコード（実際の運用では300レコード）
        """
        # テスト用デバイスの作成
        self.device = Device.objects.create(name="テスト用デバイス")

        # テスト用土地ブロックの作成 - 各ブロック位置に対応する土地ブロックを作成
        self.land_blocks = {
            "A1": LandBlock.objects.create(name="A1ブロック"),
            "A3": LandBlock.objects.create(name="A3ブロック"),
            "B2": LandBlock.objects.create(name="B2ブロック"),
            "C1": LandBlock.objects.create(name="C1ブロック"),
            "C3": LandBlock.objects.create(name="C3ブロック"),
        }

        # テスト用の計測データを作成
        self.base_datetime = timezone.now()
        self.measurements = []

        # ブロック位置とメモリ範囲の対応関係を辞書で定義
        self.block_memory_ranges = {
            "C1": range(1, 6),  # C1ブロックはメモリ1-5に対応
            "C3": range(6, 11),  # C3ブロックはメモリ6-10に対応
            "A3": range(11, 16),  # A3ブロックはメモリ11-15に対応
            "B2": range(16, 21),  # B2ブロックはメモリ16-20に対応
            "A1": range(21, 26),  # A1ブロックはメモリ21-25に対応
        }

        # メモリからブロックを逆引きするための辞書を作成
        self.memory_to_block = {}
        for block, memory_range in self.block_memory_ranges.items():
            for memory_id in memory_range:
                self.memory_to_block[memory_id] = block

        # 5つのブロック、各ブロック5点法（5メモリ）のデータを作成
        # 実際には各メモリに0-60cmまでの60レコードがあるが、テストでは簡略化
        for block, memory_range in self.block_memory_ranges.items():
            for memory_id in memory_range:
                measurement = SoilHardnessMeasurement.objects.create(
                    set_memory=memory_id,
                    set_datetime=self.base_datetime,
                    set_depth=60,  # 計測の最大深度は60cm
                    set_spring=1,
                    set_cone=1,
                    depth=1,  # すべての測定位置で1cmの深度を記録
                    pressure=100,  # 測定値を簡略化して一定値を使用
                    folder="test_folder",
                    set_device=self.device,
                )
                print(
                    f"測定データ作成: ブロック={block}, メモリ={memory_id}, 深度={measurement.depth}cm"
                )
                self.measurements.append(measurement)

        # 各メモリに対応する土地ブロックを割り当て
        # テストの目的のため、一部のブロック（C1, C3, A3）には土地ブロックを割り当てず、
        # B2とA1ブロックにのみ土地ブロックを割り当てる
        for measurement in self.measurements:
            block = self.memory_to_block.get(measurement.set_memory)
            if block in ["B2", "A1"]:  # B2とA1ブロックのみ土地ブロックを割り当て
                measurement.land_block = self.land_blocks[block]
                measurement.save()
                print(
                    f"土地ブロック割当: メモリ={measurement.set_memory}, ブロック={block}, 土地ブロック={measurement.land_block.name}"
                )

        # 設定完了後の情報表示
        print(f"\n===== 圃場データセットアップ完了 =====")
        print(f"合計測定データ: {SoilHardnessMeasurement.objects.count()}件")
        print(
            f"土地ブロック未割当: {SoilHardnessMeasurement.objects.filter(land_block__isnull=True).count()}件"
        )
        print(
            f"土地ブロック割当済: {SoilHardnessMeasurement.objects.filter(land_block__isnull=False).count()}件\n"
        )

    def test_get_measurements_by_memory_range(self):
        """
        get_measurements_by_memory_rangeメソッドのテスト

        【シナリオ】
        実際の圃場計測では、各ブロックで5点法（1ブロック内の5箇所で測定）を用いて計測を行い、
        各ブロックにメモリ番号が割り振られます。
        Rパターンでの測定順序に従い、このテストでは以下のシナリオを想定します：
        1. C1ブロック: メモリ1-5
        2. C3ブロック: メモリ6-10
        3. A3ブロック: メモリ11-15
        4. B2ブロック: メモリ16-20
        5. A1ブロック: メモリ21-25
        6. テストではメモリ1-3のみを取得したい場合、memory_range(1, 3)を指定します

        【期待される結果】
        - メモリ1-3の取得: 3個のデータ（3メモリ×1深度）
          ※実際の運用では180個（3メモリ×60深度）になります
        - メモリの分布: {1: 1, 2: 1, 3: 1}（各メモリに1つずつデータがある）
        - メモリ1のみの取得: 1個のデータ（1メモリ×1深度）
          ※実際の運用では60個（1メモリ×60深度）になります
        """
        # メモリ1から3の計測データを取得
        results = SoilHardnessMeasurementRepository.get_measurements_by_memory_range(
            1, 3
        )

        # 結果の検証
        self.assertEqual(len(results), 3)  # 3メモリ x 1深度 = 3データ
        self.assertEqual(results.first().set_memory, 1)  # 最初のデータのメモリが1
        self.assertEqual(results.last().set_memory, 3)  # 最後のデータのメモリが3

        # メモリの分布を確認
        memory_counts = {}
        for item in results:
            memory_counts[item.set_memory] = memory_counts.get(item.set_memory, 0) + 1

        # 各メモリごとに1つのデータが存在することを確認
        self.assertEqual(memory_counts, {1: 1, 2: 1, 3: 1})

        # 境界値のテスト - 1つだけのメモリデータを取得
        single_results = (
            SoilHardnessMeasurementRepository.get_measurements_by_memory_range(1, 1)
        )
        self.assertEqual(len(single_results), 1)  # 1メモリ x 1深度 = 1データ
        self.assertEqual(single_results.first().set_memory, 1)
        self.assertEqual(single_results.last().set_memory, 1)

    def test_group_measurements(self):
        """
        group_measurementsメソッドのテスト (クエリセットがNoneの場合)

        【シナリオ】
        土壌計測データは通常、以下のワークフローで処理されます：
        1. 圃場で5点法により計測を行い、各計測点にメモリ番号(set_memory)が割り振られる
        2. 計測データは一旦すべてメモリ番号だけを持ち、どの圃場のどのブロックかは未割当(land_block=None)
        3. 後で分析時に、各メモリと土地ブロックの対応付けを行う

        このテストでは、「まだブロック割当が行われていないデータ（C1, C3, A3ブロック = メモリ1-15）」をグループ化して、
        各メモリごとのデータ件数を確認します。

        【期待される結果】
        - グループ数: 15個（メモリ1-15の各グループ）
        - 各グループのカウント: 各メモリとも1（各メモリに深度データが1つあるため）
          ※実際の運用では各メモリ60レコード（0-60cmまでの深度データ）
        - 合計レコード数: 15（15グループ×1データ）
          ※実際の運用では900レコード（15グループ×60データ）

        【テスト実装における注記】
        本テストではテストの簡略化のため、C1, C3, A3ブロック（メモリ1-15）を土地ブロック未割当としており、
        B2, A1ブロック（メモリ16-25）を土地ブロック割当済みにしています。そのため、
        グループ数は15になります。実際の期待値は以下となります：
        - グループ数: 15個（メモリ1-15の各グループ）
        - 合計レコード数: 15（15グループ×1データ）
        """
        # 土地ブロックが割り当てられていないデータをグループ化
        results = SoilHardnessMeasurementRepository.group_measurements()

        # 結果の検証
        self.assertEqual(
            len(results), 15
        )  # 未割り当てデータのグループ数は15（メモリ1-15の3ブロック分）

        # 各グループの内容を検証
        # メモリ1-15の検証
        for i, group in enumerate(results, 1):  # インデックス1から開始
            # 各メモリに対して期待する結果を動的に生成
            expected = {"set_memory": i, "cnt": 1, "set_datetime": self.base_datetime}
            self.assertEqual(group["set_memory"], expected["set_memory"])
            self.assertEqual(group["cnt"], expected["cnt"])
            self.assertEqual(group["set_datetime"], expected["set_datetime"])

        # 集計されたデータの総数を確認
        total_records = sum(group["cnt"] for group in results)
        self.assertEqual(
            total_records, 15
        )  # 未割り当てデータの合計は15個（15メモリ×1深度）
        # 実際の運用では900レコード（15メモリ×60深度）になる

    def test_group_measurements_with_queryset(self):
        """
        group_measurementsメソッドのテスト (クエリセットを指定する場合)

        【実際のviewsでの使用ケース】
        HardnessAssociationIndividualViewでは、特定のメモリ範囲（25個分=5ブロック×5点法）のデータを
        取得して圃場ブロックを直接選択・割り当てる処理を行います。このビューでは:
        1. get_measurements_by_memory_rangeでメモリ範囲のデータ（１圃場ぶん）を取得
        2. 取得したクエリセットをgroup_measurementsに渡してグループ化
        3. 圃場ブロックを選択して割り当て

        このテストでは、そのようなクエリセット使用パターンをシミュレートします。

        【シナリオ1：特定メモリ範囲のデータのみを対象にする】
        圃場分析では、特定のメモリ範囲のデータだけを分析したいケースがあります。
        このシナリオでは、メモリ1-5（C1ブロック全体の5点法測定データ）をフィルタリングして集計します。
        テストデータでは、メモリ1-15が未割当（C1, C3, A3ブロック）で、そのうちC1ブロックのメモリ1-5を
        テストで使用します。実務では、このような未割当データをC1ブロックに割り当てる処理を行います。
        これはHardnessAssociationIndividualViewでの一部データ処理のシミュレーションです。

        【シナリオ2：分析済みデータのみを対象にする】
        すでに土地ブロックに割り当て済みのデータ（分析済みデータ）だけを集計したいケースがあります。
        このシナリオでは、B2ブロック（中中、メモリ16-20）とA1ブロック（右下、メモリ21-25）に割り当て済みのデータだけを集計します。
        これは、すでに割り当て済みのデータの確認や再処理を行う場合の処理パターンです。

        【期待される結果（シナリオ1）】
        - グループ数: 5つ（メモリ1-5 = C1ブロック全体の5点法データ）
        - 各グループのカウント: 各グループとも1（各メモリに深度データが1つある）
          ※実際の運用では各グループ60レコード
        - 合計: 5レコード（5グループ×1深度）※実際の運用では300レコード（5メモリ×60深度）
        - 実務では、このデータ群をC1ブロックに割り当てて土壌分析を行う

        【期待される結果（シナリオ2）】
        - グループ数: 10つ（メモリ16-25 = B2,A1ブロックに割り当て済み）
        - 各グループのカウント: 各グループとも1（各メモリに深度データが1つある）
          ※実際の運用では各グループ60レコード
        - 合計: 10レコード（10グループ×1深度）※実際の運用では600レコード
        """
        # シナリオ1: メモリ1-5のデータを対象とする（C1ブロック全体の5点法測定データ）
        # 未割当のメモリは1-15（C1, C3, A3ブロック）で、そのうちC1ブロック全体（メモリ1-5）を使用
        # 実務では、このデータをC1ブロックに割り当てる処理を行う
        # HardnessAssociationIndividualViewでの使用パターンに相当：特定のメモリ範囲を取得してグループ化
        base_queryset = SoilHardnessMeasurement.objects.filter(set_memory__lte=5)
        results = SoilHardnessMeasurementRepository.group_measurements(base_queryset)

        # 結果の検証 - グループ数
        self.assertEqual(
            len(results), 5
        )  # 5つのメモリセットがグループ化される（C1ブロック全体）

        # メモリ値が期待通りであることを確認
        memory_values = [group["set_memory"] for group in results]
        self.assertEqual(
            memory_values, [1, 2, 3, 4, 5]
        )  # メモリ1-5の順にソートされている（C1ブロック全体）

        # 各グループのカウント数を確認（C1ブロック全体の5点法データ）
        for i, group in enumerate(results, 1):
            expected_memory = i  # メモリ番号は1から始まる
            self.assertEqual(group["set_memory"], expected_memory)
            self.assertEqual(group["cnt"], 1)  # 各メモリには深度データが1つある
            self.assertEqual(group["set_datetime"], self.base_datetime)

        # シナリオ2: 土地ブロックが割り当てられたデータのみを対象とする（B2, A1ブロック = メモリ16-25）
        # すでに割り当て済みのデータの確認や再処理を行う場合の処理パターン
        with_block_queryset = SoilHardnessMeasurement.objects.filter(
            land_block__isnull=False
        )
        with_block_results = SoilHardnessMeasurementRepository.group_measurements(
            with_block_queryset
        )

        # 結果の検証 - グループ数
        self.assertEqual(
            len(with_block_results), 10
        )  # B2, A1ブロック（メモリ16-25）の10グループ

        # メモリ値の範囲が期待通りであることを確認
        memory_values = [group["set_memory"] for group in with_block_results]
        self.assertTrue(all(16 <= memory <= 25 for memory in memory_values))
        self.assertEqual(
            sorted(memory_values), list(range(16, 26))
        )  # メモリ16-25が含まれる

        # 各グループのカウント数を確認
        for group in with_block_results:
            self.assertEqual(group["cnt"], 1)  # 各メモリには深度データが1つある
            # 実際の運用では各メモリに60レコード（0-60cmまでの深度データ）が含まれる
            self.assertEqual(group["set_datetime"], self.base_datetime)

        # 総レコード数の確認
        total_records = sum(group["cnt"] for group in with_block_results)
        self.assertEqual(
            total_records, 10
        )  # 割り当て済みデータの合計は10個（10メモリ×1深度）
        # 実際の運用では600レコード（10メモリ×60深度）になる
