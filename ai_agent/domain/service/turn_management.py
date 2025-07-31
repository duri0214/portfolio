from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.thinking_engines.cloud_act_pdf import CloudActPdfService
from ai_agent.domain.service.thinking_engines.declining_birth_rate_pdf import (
    DecliningBirthRatePdfService,
)
from ai_agent.domain.service.thinking_engines.googlemaps_review import (
    GoogleMapsReviewService,
)
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
    def can_respond_to_input(entity: Entity, input_text: str) -> bool:
        """
        エンティティが入力テキストに応答可能かどうかを判断します。

        各エンティティのthinking_typeに基づいて適切な思考エンジンサービスを選択し、
        入力テキストに対してそのエンティティが応答可能かどうかを評価します。
        例えば、「レストラン」というキーワードはGoogleMapsReviewServiceがうまく処理できます。
        「法律」というキーワードはCloudActPdfServiceがうまく処理できます。

        処理の流れ：
        1. エンティティのthinking_typeを確認
        2. 適切な専門サービスに入力テキストを渡す
        3. 専門サービスの判断結果（True/False）を返す

        サポートされている思考エンジン：
        - GoogleMapsReviewService: 地図・レビュー関連の質問に対応
        - CloudActPdfService: 法律文書・クラウド関連の質問に対応
        - DecliningBirthRatePdfService: 少子化・人口動態関連の質問に対応

        重要な動作：
        - 各思考エンジンは入力テキストが自分の専門領域に関連するかを判断します
        - エンティティのthinking_typeに適さない入力の場合はFalseを返します
          （例：GoogleMapsベースのエンティティに法律の質問をした場合はFalse）
        - Falseが返された場合、そのエンティティは応答せず、他のエンティティが応答機会を得ます

        Args:
            entity (Entity): 応答可能性を評価するエンティティ
            input_text (str): 評価する入力テキスト

        Returns:
            bool: 応答可能な場合はTrue、そうでない場合はFalse
        """
        if entity.thinking_type == "google_maps_based":
            return GoogleMapsReviewService.can_respond(input_text, entity)

        elif entity.thinking_type == "cloud_act_based":
            return CloudActPdfService.can_respond(input_text, entity)

        elif entity.thinking_type == "declining_birth_rate_based":
            return DecliningBirthRatePdfService.can_respond(input_text, entity)

        # 未知のthinking_typeの場合はデフォルトで発言可能
        # これにより、新しい思考エンジンが追加された場合でもシステムが動作し続ける
        return True
