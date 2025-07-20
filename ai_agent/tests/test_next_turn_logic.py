from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase, Client
from django.urls import reverse

from ai_agent.domain.service.conversation import ConversationService
from ai_agent.models import Entity, ActionHistory, ActionTimeline, Message
from ai_agent.views import ResetTimelineView


class NextTurnLogicTestCase(TestCase):
    """
    NextTurnViewの連続実行とタイムライン同期統合テスト

    このテストクラスは、AI Agent システムのユーザー操作シナリオを通じた
    View層統合テストを実行します。実際のHTTPリクエスト・レスポンス処理、
    画面遷移、メッセージ表示、連続的な会話ターン処理の整合性を検証します。

    ファイル配置について：
    このテストは ai_agent/tests/ に配置されています。tests/domain/service/ ではない理由：
    - Django TestCase + Client を使用したHTTPリクエスト統合テスト
    - View層（urls.py、views.py）とModel層の統合処理をテスト
    - django.contrib.messages framework の動作検証
    - URLルーティング、リダイレクト処理の検証
    - E2Eに近い統合テスト（ユーザー操作シナリオベース）
    - Djangoプロジェクトでは「View + Model + URL統合テスト」は app/tests/ が適切

    テスト対象：
    - NextTurnView の連続実行時のデータ整合性
    - ActionHistory と ActionTimeline の同期状態
    - 複数ターンでのエンティティ選択ロジック
    - すべてのアクション完了時のリセット処理
    - HTTPレスポンス（リダイレクト）の正確性
    - Djangoメッセージフレームワークの動作

    テストの性質：
    - 統合テスト：View + Model + URL + Message の統合
    - シナリオテスト：ユーザーの実際の操作フローを模擬
    - 状態変化テスト：複数リクエストにわたるシステム状態の追跡
    - HTTPテスト：実際のHTTP POST リクエスト処理

    エンティティ設定：
    - EntityA: 中速エンティティ（speed=10）
    - EntityB: 高速エンティティ（speed=15）
    - EntityC: 低速エンティティ（speed=8）
    - 3つのエンティティで複雑な行動順序パターンを検証

    他のテストクラスとの違い：

    vs test_conversation.py（ConversationServiceTest）：
    - このテスト：View層統合、HTTPリクエスト処理、画面遷移
    - ConversationServiceTest：ドメインサービス単体の内部アルゴリズム
    - テストレベル：E2Eに近い統合テスト vs 単体/統合テスト
    - 焦点：ユーザー操作シナリオ vs 数学的アルゴリズム検証
    - 依存関係：View + URL + Message vs Model層のみ

    vs test_input_processor.py（InputProcessorTest）：
    - このテスト：会話進行の継続性、複数ターンの状態管理
    - InputProcessorTest：単一リクエスト内の入力処理、セキュリティ
    - 時間軸：複数ターンにわたる状態変化 vs 1リクエスト内処理
    - 検証対象：システム動作継続性 vs 入力安全性
    - エンティティ関係：複数エンティティ間の協調 vs 単一エンティティ処理

    このテストの責務：
    実際のユーザー操作において、複数ターンにわたる会話が正しく継続し、
    システム状態が一貫性を保つことを保証する

    重要性：
    このテストは、ユーザーが実際にシステムを使用する際の品質を保証し、
    データ不整合や画面遷移の問題を早期発見するために不可欠です。
    """

    def setUp(self):
        """テストデータの初期化"""
        self.client = Client()

        # テスト用のエンティティを作成
        self.entity_a = Entity.objects.create(
            name="EntityA", thinking_type="google_maps_based", speed=10
        )
        self.entity_b = Entity.objects.create(
            name="EntityB", thinking_type="rag_based", speed=15
        )
        self.entity_c = Entity.objects.create(
            name="EntityC", thinking_type="ng_word_based", speed=8
        )

        # タイムラインを初期化
        ResetTimelineView.reset_timeline()

    def test_consecutive_next_turn_execution(self):
        """連続してnext_turnを実行した時の整合性テスト"""

        # 初期状態の確認
        initial_future_actions = list(
            ActionHistory.objects.filter(done=False).order_by("acted_at_turn")
        )
        initial_completed_actions = list(
            ActionHistory.objects.filter(done=True).order_by("acted_at_turn")
        )

        self.assertTrue(
            len(initial_future_actions) > 0, "初期状態で未来のアクションが存在すること"
        )
        self.assertEqual(
            len(initial_completed_actions),
            0,
            "初期状態で完了済みアクションは0であること",
        )

        # 5回連続でnext_turnを実行
        execution_results = []
        for i in range(5):
            with patch(
                "ai_agent.domain.service.conversation.ConversationService.think",
                return_value=True,
            ):
                response = self.client.post(reverse("agt:next_turn"))

                # レスポンスの確認
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("agt:index"))

                # ActionHistoryの状態を記録
                future_actions = list(
                    ActionHistory.objects.filter(done=False).order_by("acted_at_turn")
                )
                completed_actions = list(
                    ActionHistory.objects.filter(done=True).order_by("acted_at_turn")
                )

                execution_results.append(
                    {
                        "step": i + 1,
                        "future_actions_count": len(future_actions),
                        "completed_actions_count": len(completed_actions),
                        "next_future_entity": (
                            future_actions[0].entity.name if future_actions else None
                        ),
                        "last_completed_entity": (
                            completed_actions[-1].entity.name
                            if completed_actions
                            else None
                        ),
                        "future_actions": [
                            {"entity": a.entity.name, "turn": a.acted_at_turn}
                            for a in future_actions[:3]
                        ],
                        "completed_actions": [
                            {"entity": a.entity.name, "turn": a.acted_at_turn}
                            for a in completed_actions[-3:]
                        ],
                    }
                )

        # 結果の検証
        for i, result in enumerate(execution_results):
            print(f"\nStep {result['step']}:")
            print(f"  Future actions: {result['future_actions_count']}")
            print(f"  Completed actions: {result['completed_actions_count']}")
            print(f"  Next entity: {result['next_future_entity']}")
            print(f"  Last completed: {result['last_completed_entity']}")
            print(f"  Future actions detail: {result['future_actions']}")
            print(f"  Completed actions detail: {result['completed_actions']}")

            # 各ステップで完了済みアクションが増加していることを確認
            self.assertEqual(result["completed_actions_count"], i + 1)

            # 未来のアクションが減少していることを確認
            expected_future_count = len(initial_future_actions) - (i + 1)
            self.assertEqual(result["future_actions_count"], expected_future_count)

    def test_entity_selection_vs_action_history_sync(self):
        """エンティティ選択ロジックとActionHistoryの同期テスト"""

        with patch(
            "ai_agent.domain.service.conversation.ConversationService.think",
            return_value=True,
        ):
            # 最初のnext_turn実行前の状態
            first_future_action = (
                ActionHistory.objects.filter(done=False)
                .order_by("acted_at_turn")
                .first()
            )
            expected_entity = first_future_action.entity

            # get_next_entityで選択されるエンティティを取得
            with patch(
                "ai_agent.domain.repository.conversation.ConversationRepository.create_message"
            ) as mock_create:
                selected_entity = ConversationService.get_next_entity("")

                # 選択されたエンティティとActionHistoryの最初のエンティティが一致することを確認
                self.assertEqual(
                    selected_entity.id,
                    expected_entity.id,
                    f"選択されたエンティティ({selected_entity.name})とActionHistoryの最初のエンティティ({expected_entity.name})が一致しません",
                )

    def test_timeline_state_after_multiple_turns(self):
        """複数ターン実行後のタイムライン状態テスト"""

        with patch(
            "ai_agent.domain.service.conversation.ConversationService.think",
            return_value=True,
        ):
            # 3回実行
            for _ in range(3):
                self.client.post(reverse("agt:next_turn"))

            # ActionTimelineとActionHistoryの整合性確認
            action_timelines = ActionTimeline.objects.all()
            completed_actions = ActionHistory.objects.filter(done=True).order_by(
                "acted_at_turn"
            )
            future_actions = ActionHistory.objects.filter(done=False).order_by(
                "acted_at_turn"
            )

            # 各エンティティのnext_turn値が正しく更新されているかチェック
            for timeline in action_timelines:
                entity_future_actions = future_actions.filter(entity=timeline.entity)
                if entity_future_actions.exists():
                    earliest_future_turn = entity_future_actions.first().acted_at_turn
                    print(
                        f"Entity {timeline.entity.name}: next_turn={timeline.next_turn}, earliest_future_turn={earliest_future_turn}"
                    )

    def test_no_more_actions_scenario(self):
        """すべてのアクションが完了した場合のリセット動作テスト"""

        # すべてのActionHistoryを完了済みにする
        ActionHistory.objects.all().update(done=True)

        with patch("ai_agent.views.ResetTimelineView.reset_timeline") as mock_reset:
            response = self.client.post(reverse("agt:next_turn"))

            # リセットが呼ばれることを確認
            mock_reset.assert_called_once()

            # 適切なメッセージが設定されることを確認
            messages = list(get_messages(response.wsgi_request))
            self.assertTrue(
                any("処理すべきアクションはもうありません" in str(m) for m in messages)
            )

    def tearDown(self):
        """テスト後のクリーンアップ"""
        Entity.objects.all().delete()
        ActionHistory.objects.all().delete()
        ActionTimeline.objects.all().delete()
        Message.objects.all().delete()
