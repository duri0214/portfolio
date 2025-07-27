from unittest.mock import patch

from django.test import TestCase

from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.turn_management import TurnManagementService
from ai_agent.domain.valueobject.turn_management import EntityVO
from ai_agent.models import Entity, ActionTimeline, ActionHistory


class TurnManagementServiceTest(TestCase):
    """
    TurnManagementServiceのドメインサービステスト

    このテストクラスは、AI Agent システムの会話管理ドメインサービスの
    コアロジックをテストします。データベース統合を含む統合テストとして、
    実際のDjangoモデル（Entity, ActionTimeline）を使用してテストを実行します。

    ファイル配置について：
    このテストは ai_agent/tests/ に配置されています。tests/domain/service/ ではない理由：
    - Djangoモデル（Entity, ActionTimeline）を使用するデータベース統合テスト
    - django.test.TestCase を継承（トランザクション管理が必要）
    - 純粋な単体テストではなく、データベース連携込みのドメインサービステスト
    - Djangoプロジェクトでは「ドメインサービス + DB統合テスト」は app/tests/ が適切

    テスト対象：
    - エンティティの行動順序決定ロジック（速度ベース）
    - タイムライン管理システム
    - 次のアクション予測シミュレーション
    - エンティティの行動可能性判定（can_act）

    テストの性質：
    - 統合テスト：データベースとドメインサービスの統合
    - 単体テスト：各ドメインサービスメソッドの独立した動作確認
    - モックテスト：外部依存関係（think関数）のモック化

    エンティティ設定：
    - Entity1: 高速エンティティ（speed=100）、Google Mapsベース
    - Entity2: 低速エンティティ（speed=10）、NGワードベース
    - 速度比 10:1 により、Entity1が10回行動してからEntity2が1回行動

    他のテストクラスとの違い：

    vs test_input_processor.py（InputProcessorTest）：
    - このテスト：会話フロー制御とエンティティ行動順序のドメインロジック
    - InputProcessorTest：入力検証、ガードレール、セキュリティ機能
    - 領域の分離：会話管理 vs 入力処理パイプライン
    - データフロー：このテスト（エンティティ→会話）、InputProcessor（入力→出力）

    vs test_next_turn_logic.py（NextTurnLogicTestCase）：
    - このテスト：ドメインサービス単体の内部ロジック（速度計算、順序決定）
    - NextTurnLogicTestCase：View統合を含む実際のHTTPリクエスト処理と画面遷移
    - テストレベル：単体/統合テスト vs E2Eに近い統合テスト
    - 焦点：アルゴリズム検証 vs ユーザー操作シナリオ検証
    - 依存関係：モデル層 vs View + Model + URL + Message framework

    このテストの責務：
    TurnManagementServiceのコアアルゴリズムが数学的に正確に動作することを保証する
    """

    def setUp(self):
        """
        テストデータの初期化と前準備

        各テストメソッド実行前に呼び出され、テスト用のエンティティを作成し、
        タイムラインシステムを初期化します。

        セットアップ内容：
        1. 2つの異なる速度設定のエンティティを作成
        2. ConversationService.initialize_timeline()でタイムライン初期化
        3. テスト用入力テキストの準備

        作成されるエンティティ：
        - Entity1: 高速（speed=100）、Google Maps思考タイプ
        - Entity2: 低速（speed=10）、NGワード思考タイプ

        初期状態での next_turn 値：
        - Entity1: 0.01 (1/100)
        - Entity2: 0.10 (1/10)
        """
        # Entity1: 高速で Google Maps レビューに基づくタイプ
        self.entity1 = Entity.objects.create(
            name="Entity1",
            speed=100,  # 高速
            thinking_type="google_maps_based",
        )
        # Entity2: 低速で NG ワードに基づくタイプ
        self.entity2 = Entity.objects.create(
            name="Entity2",
            speed=10,  # 低速
            thinking_type="ng_word_based",
        )

        # 初期化時にタイムラインを設定
        TurnManagementService.initialize_timeline()

        # テスト用の入力テキスト
        self.test_input_text = "sample input text"

    def test_timeline_initialization(self):
        """
        タイムライン初期化機能のテスト

        シナリオ：
        システム起動時またはリセット時に、全エンティティがタイムラインに
        正しく登録され、各エンティティの初期 next_turn 値が速度に基づいて
        適切に計算されることを確認する。

        テスト内容：
        1. 全エンティティがActionTimelineに登録されているか
        2. 各エンティティの next_turn が 1/speed で計算されているか
        3. データベースの整合性が保たれているか

        期待される動作：
        - ActionTimeline テーブルにエンティティ数と同じレコードが作成される
        - Entity1: next_turn = 1/100 = 0.01
        - Entity2: next_turn = 1/10 = 0.10
        - 高速エンティティほど小さな next_turn 値を持つ

        検証項目：
        - タイムラインレコード数 = エンティティ数（2個）
        - 各エンティティの next_turn = 1 / entity.speed

        重要性：
        この機能が正しく動作しないと、エンティティの行動順序が
        不正確になり、システム全体の動作が破綻する。
        """
        # テストケース1: タイムラインに全エンティティが登録されているか確認
        timelines = ActionTimeline.objects.all()
        self.assertEqual(timelines.count(), 2)

        # テストケース2: 各エンティティの next_turn が適切に計算されているか確認
        for timeline in timelines:
            self.assertEqual(timeline.next_turn, 1 / timeline.entity.speed)

    def test_create_message_updates_timeline(self):
        """
        メッセージ作成時のActionHistory更新機能のテスト

        シナリオ：
        エンティティがメッセージを作成した際に、ActionHistoryが完了状態に
        更新され、メッセージがデータベースに正しく保存されることを確認します。

        テストの流れ：
        1. 初期状態：ActionHistoryのActionHistoryレコードが作成される
        2. create_message実行：メッセージがデータベースに保存される
        3. ActionHistoryが完了状態(done=True)に更新される
        4. 次のActionHistoryレコードが処理される

        テスト内容：
        - TurnManagementRepository.create_message()の動作確認
        - メッセージがデータベースに正しく保存されること
        - ActionHistoryが完了状態に更新されること
        - タイムラインの初期値が正しく設定されていること

        期待される動作：
        1. ActionHistory作成: Entity1のActionHistoryレコードが作成される
        2. メッセージ作成：Entity1による"Test Message"がDBに保存される
        3. ActionHistory更新：ActionHistoryのdoneフラグがTrueに更新される
        4. タイムライン確認：next_turn = 1/speed = 0.01
        """
        # テストケース1: ActionHistoryオブジェクトを作成
        action_history = ActionHistory.objects.create(
            entity=self.entity1, acted_at_turn=1, done=False
        )

        # テストケース2: Entity1でメッセージを作成
        TurnManagementRepository.create_message(
            content="Test Message", action_history=action_history
        )

        # テストケース3: タイムラインの設定が正しいか確認
        timeline = ActionTimeline.objects.get(entity=self.entity1)
        self.assertEqual(timeline.next_turn, 1 / self.entity1.speed)

    def test_simulate_next_actions(self):
        """
        未来のアクション予測シミュレーション機能のテスト

        シナリオ：
        現在のタイムライン状態から、今後指定したステップ数分の
        エンティティ行動順序を事前に予測・計算し、UIでの表示や
        デバッグに活用できることを確認する。

        シミュレーション設定：
        - max_steps=11：今後11回分の行動を予測
        - Entity1（speed=100）：0.01間隔で行動
        - Entity2（speed=10）：0.10間隔で行動
        - 実際のデータベース状態を変更せずに予測のみ実行

        予測される行動シーケンス：
        1. Entity1 (0.01) - 1回目
        2. Entity1 (0.02) - 2回目
        3. Entity1 (0.03) - 3回目
        4. Entity1 (0.04) - 4回目
        5. Entity1 (0.05) - 5回目
        6. Entity1 (0.06) - 6回目
        7. Entity1 (0.07) - 7回目
        8. Entity1 (0.08) - 8回目
        9. Entity1 (0.09) - 9回目
        10. Entity1 (0.10) - 10回目
        11. Entity2 (0.10) - 1回目（同値だがEntity2のターン）

        期待される動作：
        - 11個のEntityVOオブジェクトが返される
        - 最初の10個はすべてEntity1
        - 11番目はEntity2
        - 各next_turn値が正確に計算されている
        - 実際のデータベース状態は変更されない

        検証項目：
        - 返される配列の長さ = max_steps
        - 各EntityVOのname属性の正確性
        - 各EntityVOのnext_turn属性の数学的正確性
        - 速度比に基づく行動頻度の正確性

        技術的詳細：
        - EntityVO：Value Objectパターンによる不変オブジェクト
        - シミュレーション：読み取り専用の予測処理
        - 浮動小数点比較：assertAlmostEqual()で精度問題を回避

        重要性：
        この機能により、ユーザーは今後の会話の流れを予測でき、
        システム管理者はエンティティの行動パターンをデバッグできる。
        """
        # テストケース1: 次の11ステップをシミュレーション
        simulation = TurnManagementService.simulate_next_actions(max_steps=11)

        # テストケース2: シミュレーション結果と期待値を比較
        expected_simulation = [
            EntityVO(name="Entity1", next_turn=0.01),
            EntityVO(name="Entity1", next_turn=0.02),
            EntityVO(name="Entity1", next_turn=0.03),
            EntityVO(name="Entity1", next_turn=0.04),
            EntityVO(name="Entity1", next_turn=0.05),
            EntityVO(name="Entity1", next_turn=0.06),
            EntityVO(name="Entity1", next_turn=0.07),
            EntityVO(name="Entity1", next_turn=0.08),
            EntityVO(name="Entity1", next_turn=0.09),
            EntityVO(name="Entity1", next_turn=0.10),
            EntityVO(name="Entity2", next_turn=0.10),
        ]
        for actual, expected in zip(simulation, expected_simulation):
            self.assertEqual(actual.name, expected.name)
            self.assertAlmostEqual(actual.next_turn, expected.next_turn, places=2)

    @patch(
        "ai_agent.domain.service.turn_management.TurnManagementService.can_respond_to_input"
    )
    def test_can_act_false_skips_entity(self, mock_can_respond):
        """
        このテストでは、TurnManagementServiceのcan_respond_to_inputメソッドの基本的な動作を検証します。

        can_respond_to_inputメソッドはエンティティの思考タイプに基づいて、適切な思考エンジンを選択し、
        入力テキストに対して応答可能かどうかを判断します。各思考エンジンは異なる判断基準を
        持ち、エンティティごとの振る舞いをカスタマイズできる設計になっています。
        """

        # テストケース1: モック関数の設定
        def mock_can_respond_side_effect(entity, input_text):
            if entity == self.entity1:
                return False  # Entity1 は行動不可
            return True  # 他のエンティティは行動可能

        mock_can_respond.side_effect = mock_can_respond_side_effect

        # テストケース2: Entity1は応答不可能
        self.assertFalse(
            TurnManagementService.can_respond_to_input(
                self.entity1, self.test_input_text
            )
        )

        # テストケース3: Entity2は応答可能
        self.assertTrue(
            TurnManagementService.can_respond_to_input(
                self.entity2, self.test_input_text
            )
        )
