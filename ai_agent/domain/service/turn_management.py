from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.thinking_engines.googlemaps_review import (
    GoogleMapsReviewService,
)
from ai_agent.domain.service.thinking_engines.ng_word import NGWordService
from ai_agent.domain.service.thinking_engines.rag import RagService
from ai_agent.domain.valueobject.turn_management import EntityVO
from ai_agent.models import Entity, ActionHistory


class TurnManagementService:
    @staticmethod
    def calculate_next_turn_increment(speed: float) -> float:
        """
        エンティティの速度に基づいてnext_turnの増分を計算します。
        この方法により、増分の導出方法に一貫性が保たれ、将来の調整が容易になります。

        Args:
            speed (float): エンティティの速度値

        Returns:
            float: 次のターンまでの増分値（1/speed）
        """
        return 1 / speed

    @staticmethod
    def initialize_timeline():
        """
        エンティティの速度に基づいて最初のターン値を割り当て、タイムラインを初期化します。

        各エンティティのActionTimelineレコードを作成または更新し、next_turn値を設定します。
        この初期化により、エンティティの行動順序が速度に応じて決定されます。
        """
        entities = TurnManagementRepository.get_all_entities()
        for entity in entities:
            TurnManagementRepository.update_or_create_action_timeline(
                entity=entity,
                defaults={
                    "next_turn": TurnManagementService.calculate_next_turn_increment(
                        entity.speed
                    )
                },
            )

    @staticmethod
    def get_next_entity(input_text: str):
        """
        タイムラインに基づいて次に行動するエンティティを取得します。
        各エンティティの発言可能状態（`can_act`）は`think`メソッドによって決定されます。

        複数のエンティティが同じnext_turnを持つ場合は、エンティティIDの昇順で選択されます。
        これにより、同じタイミングで行動可能な複数のエンティティがあっても、
        常に決定論的に一意のエンティティが選択されます。

        Args:
            input_text (str): エンティティの`think`プロセスに渡す入力テキスト

        Returns:
            Entity: 次に行動すべきエンティティ

        Raises:
            ValueError: 行動可能なエンティティが存在しない場合
        """
        timelines = TurnManagementRepository.get_timelines_ordered_by_next_turn()
        if not timelines.exists():
            raise ValueError("タイムラインにエンティティが存在しません。")

        candidates = []
        for timeline in timelines:
            timeline.can_act = TurnManagementService.think(timeline.entity, input_text)
            timeline.save()
            if timeline.can_act:
                candidates.append(timeline)

        # 次の行動順 (next_turn) 最小値のエンティティを選択する
        if candidates:
            next_action = min(candidates, key=lambda t: (t.next_turn, t.entity.id))
            TurnManagementRepository.update_next_turn(
                action_timeline=next_action,
                increment=TurnManagementService.calculate_next_turn_increment(
                    next_action.entity.speed
                ),
            )
            return next_action.entity

        # このターンでは発言可能なエンティティがいない場合、すべてのエンティティの next_turn を更新して次のターンへ進む
        for timeline in timelines:
            TurnManagementRepository.update_next_turn(
                action_timeline=timeline,
                increment=TurnManagementService.calculate_next_turn_increment(
                    timeline.entity.speed
                ),
            )
        raise ValueError("このターンで行動可能なエンティティが存在しません。")

    @staticmethod
    def simulate_next_actions(max_steps=10) -> list[EntityVO]:
        """
        最大`max_steps`回数の次のエンティティアクションのシーケンスをシミュレーションし、
        各アクションに対応するActionHistoryレコードを作成します。

        next_turnが同じエンティティが複数存在する場合は、エンティティIDの昇順で選択されます。
        min関数とタプルによる複合キー比較（next_turn, entity.id）を使用することで、
        常に決定論的な順序でエンティティが選択されます。

        Args:
            max_steps (int): シミュレーションするアクションの数

        Returns:
            List[EntityVO]: エンティティ名と行動ターンを含むEntityVOオブジェクトのリスト

        Raises:
            ValueError: タイムラインにエンティティが存在しない場合
        """
        timelines = list(TurnManagementRepository.get_timelines_ordered_by_next_turn())
        if not timelines:
            raise ValueError("タイムラインにエンティティが存在しません。")

        simulation = []
        for i in range(1, max_steps + 1):
            # 次の行動を決定 (next_turn が最小のタイムラインを選ぶ)
            next_action = min(timelines, key=lambda t: (t.next_turn, t.entity.id))

            # ActionHistory レコードを作成
            ActionHistory.objects.create(
                entity=next_action.entity,
                acted_at_turn=i,
                done=False,
            )

            # シミュレーションの結果を保存
            simulation.append(
                EntityVO(name=next_action.entity.name, next_turn=next_action.next_turn)
            )

            # 次の行動予定を仮で更新
            next_action.next_turn += (
                TurnManagementService.calculate_next_turn_increment(
                    next_action.entity.speed
                )
            )

        return simulation

    @staticmethod
    def think(entity: Entity, input_text: str):
        """
        エンティティの思考ロジックを処理し、応答可能かどうかを判断します。

        エンティティのthinking_typeに基づいて適切な判断サービスを選択し、
        入力テキストに対して応答可能かどうかを評価します。

        Args:
            entity (Entity): 思考プロセスを実行するエンティティ
            input_text (str): 評価する入力テキスト

        Returns:
            bool: 応答可能な場合はTrue、そうでない場合はFalse
        """
        if entity.thinking_type == "google_maps_based":
            return GoogleMapsReviewService.can_respond(input_text, entity)

        elif entity.thinking_type == "rag_based":
            return RagService.can_respond(input_text, entity)

        elif entity.thinking_type == "ng_word_based":
            return NGWordService.can_respond(input_text, entity)

        # デフォルトで発言可能
        return True
