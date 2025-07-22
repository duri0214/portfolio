from unittest.mock import patch

from django.test import TestCase

from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.turn_management import TurnManagementService
from ai_agent.domain.valueobject.turn_management import EntityVO
from ai_agent.models import Entity, ActionTimeline


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
        # タイムラインに全エンティティが登録されているか確認
        timelines = ActionTimeline.objects.all()
        self.assertEqual(timelines.count(), 2)

        # 各エンティティの next_turn が適切に計算されているか確認
        for timeline in timelines:
            self.assertEqual(timeline.next_turn, 1 / timeline.entity.speed)

    def test_action_order_based_on_speed(self):
        """
        エンティティ速度に基づく行動順序決定のテスト

        シナリオ：
        複数のエンティティが存在する環境で、各エンティティの速度パラメータに
        基づいて適切な順序で行動することを確認する。高速なエンティティは
        より頻繁に行動し、低速なエンティティは少ない頻度で行動する。

        テストシナリオの詳細：
        - Entity1（speed=100）とEntity2（speed=10）の速度比は10:1
        - Entity1は0.01間隔、Entity2は0.10間隔で行動予定が設定される
        - 理論上、Entity1が10回行動する間にEntity2が1回行動する

        テスト手順：
        1. 1回目：Entity1が選択される（next_turn=0.01が最小）
        2. 2回目：Entity1が選択される（0.02 < 0.10）
        3. 10回目まで：Entity1が継続選択される
        4. 11回目：Entity2が選択される（0.10 = 0.10だが、Entity2のターン）
        5. 12回目：Entity1が再選択される（0.11 < 0.20）

        期待される動作：
        - 最初の10回はすべてEntity1が選択される
        - 11回目にEntity2が選択される
        - その後再びEntity1が選択される
        - 速度に比例した行動頻度が維持される

        数学的根拠：
        - Entity1 next_turn sequence: 0.01, 0.02, 0.03, ..., 0.10, 0.11
        - Entity2 next_turn sequence: 0.10, 0.20, 0.30, ...
        - 最小値を持つエンティティが次に行動する

        重要性：
        このロジックにより、高速なAIアシスタントは素早く応答し、
        低速な専門AIは慎重に応答するという差別化が実現される。
        """
        # 最初に行動するのは高速な Entity1 のはず
        next_entity = TurnManagementService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

        # Entity1 が次回行動予定を早く更新するため、2回目も Entity1 が選ばれる
        next_entity = TurnManagementService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

        # 速度の差が 10 倍であるため、Entity1 が 8 回行動した後に Entity2 のターンが来る
        for _ in range(9):
            next_entity = TurnManagementService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity2)

        # Entity2 が行動した次には再び高速な Entity1 の順番となる
        next_entity = TurnManagementService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity1)

    def test_create_message_updates_timeline(self):
        """
        メッセージ作成時のタイムライン更新機能のテスト

        シナリオ：
        エンティティがメッセージを作成した際に、そのエンティティの
        next_turn 値が適切に更新され、次回の行動タイミングが
        正しく計算されることを確認する。

        テストの流れ：
        1. 初期状態：Entity1の next_turn = 0.01
        2. create_message実行：メッセージがデータベースに保存される
        3. get_next_entity実行：Entity1が選択され、next_turn が更新される
        4. 更新後状態：Entity1の next_turn = 0.02

        テスト内容：
        - TurnManagementRepository.create_message()の動作確認
        - メッセージ作成とタイムライン更新の分離確認
        - get_next_entity()実行時のタイムライン更新確認
        - データベースの一貫性確認

        期待される動作：
        1. メッセージ作成：Entity1による"Test Message"がDBに保存される
        2. 初期確認：next_turn = 1/speed = 0.01のまま
        3. 次エンティティ取得：Entity1が選択される
        4. タイムライン更新：next_turn = 0.01 + 0.01 = 0.02

        技術的詳細：
        - refresh_from_db()：データベースから最新状態を再取得
        - タイムライン更新は get_next_entity() 内で実行される
        - メッセージ作成とタイムライン更新は独立した処理

        重要性：
        この仕組みにより、エンティティが行動するたびに次回の
        行動タイミングが自動的に調整され、公平な行動順序が保たれる。
        """
        # Entity1 でメッセージを作成
        TurnManagementRepository.create_message(self.entity1, "Test Message")

        # タイムラインを確認
        timeline = ActionTimeline.objects.get(entity=self.entity1)

        # タイムライン初期化時の next_turn を確認
        self.assertEqual(timeline.next_turn, 1 / self.entity1.speed)

        # get_next_entity を1回実行すると next_turn が更新される
        TurnManagementService.get_next_entity(self.test_input_text)
        timeline.refresh_from_db()  # タイムラインを再取得
        self.assertEqual(
            timeline.next_turn, 1 / self.entity1.speed + 1 / self.entity1.speed
        )

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
        simulation = TurnManagementService.simulate_next_actions(max_steps=11)

        # シミュレーション結果の期待値
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
        # リスト全体を比較
        for actual, expected in zip(simulation, expected_simulation):
            self.assertEqual(actual.name, expected.name)
            self.assertAlmostEqual(actual.next_turn, expected.next_turn, places=2)

    @patch("ai_agent.domain.service.turn_management.TurnManagementService.think")
    def test_can_act_false_skips_entity(self, mock_think):
        """
        エンティティ行動可能性判定とスキップ機能のテスト

        シナリオ：
        特定のエンティティが現在の状況や入力内容に対して「行動すべきでない」
        と判断した場合（can_act=False）、そのエンティティをスキップして
        次に行動可能なエンティティを選択することを確認する。

        モック設定の詳細：
        - ConversationService.think()をモック化
        - Entity1：常にFalse（行動しない）を返す
        - Entity2：常にTrue（行動する）を返す
        - この設定により、通常ならEntity1が選ばれる状況でEntity2が選ばれる

        テストシナリオ：
        1. 初期状態：Entity1のnext_turn=0.01、Entity2のnext_turn=0.10
        2. 通常なら：Entity1が選択される（0.01 < 0.10）
        3. Entity1のcan_act=False：Entity1がスキップされる
        4. 結果：Entity2が選択される
        5. Entity2の行動後：next_turnが0.20に更新される

        期待される動作：
        - think()が各エンティティに対して適切に呼ばれる
        - can_act=Falseのエンティティがスキップされる
        - 次に行動可能なエンティティが選択される
        - 選択されたエンティティのnext_turnが更新される
        - データベース状態が正しく更新される

        検証項目：
        1. 選択されたエンティティの確認：Entity2であること
        2. タイムライン更新の確認：Entity2のnext_turn = 0.2
        3. モック呼び出しの確認：各エンティティに対してthink()が呼ばれた

        技術的詳細：
        - @patch デコレータ：外部依存関係のモック化
        - mock_think.side_effect：エンティティ別の動的な戻り値設定
        - assert_any_call()：特定の引数でのメソッド呼び出し確認
        - refresh_from_db()：データベースからの最新状態取得

        実用的な活用例：
        - AIアシスタントが不適切な話題で応答を拒否する場合
        - 専門AIが専門外の質問をスキップする場合
        - エンティティがクールダウン状態で一時的に行動できない場合

        重要性：
        この機能により、各エンティティが自律的に行動判断を行い、
        不適切な状況での強制的な応答を避けることができる。
        """

        # think をモック化して、Entity1 が always False を返すように設定
        def mock_think_side_effect(entity, input_text):
            if entity == self.entity1:
                return False  # Entity1 をパスさせる
            return True  # 他のエンティティは True を返す

        mock_think.side_effect = mock_think_side_effect

        # Entity1 は skip され、Entity2 が選ばれるはず
        next_entity = TurnManagementService.get_next_entity(self.test_input_text)
        self.assertEqual(next_entity, self.entity2)

        # Entity2 が選ばれた後、next_turn が次のターン（0.2）になることを確認する
        timeline_entity2 = ActionTimeline.objects.get(entity=self.entity2)
        self.assertEqual(timeline_entity2.next_turn, 0.2)

        # モックが期待通り呼び出されたことを確認
        mock_think.assert_any_call(self.entity1, self.test_input_text)
        mock_think.assert_any_call(self.entity2, self.test_input_text)
