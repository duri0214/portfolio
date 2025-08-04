from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.valueobject.turn_management import EntityVO
from ai_agent.models import ActionHistory


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

        各エンティティのnext_turn値を設定します。
        この初期化により、エンティティの行動順序が速度に応じて決定されます。
        """
        entities = TurnManagementRepository.get_entities_ordered()
        for entity in entities:
            entity.next_turn = TurnManagementService.calculate_next_turn_increment(
                entity.speed
            )
            entity.save()

    @staticmethod
    def simulate_next_actions(max_steps=10) -> list[EntityVO]:
        """
        最大`max_steps`回数の次のエンティティアクションのシーケンスをシミュレーションし、
        各アクションに対応するActionHistoryレコードを作成します。

        next_turnが同じエンティティが複数存在する場合は、エンティティIDの昇順で選択されます。
        min関数とタプルによる複合キー比較（next_turn, id）を使用することで、
        常に決定論的な順序でエンティティが選択されます。

        Args:
            max_steps (int): シミュレーションするアクションの数

        Returns:
            List[EntityVO]: エンティティ名と行動ターンを含むEntityVOオブジェクトのリスト。
            エンティティが存在しない場合は空リストを返します。
        """
        entities = list(TurnManagementRepository.get_entities_ordered())
        if not entities:
            return []

        simulation = []
        for i in range(1, max_steps + 1):
            # 次の行動を決定 (next_turn が最小のエンティティを選ぶ)
            next_entity = min(entities, key=lambda e: (e.next_turn, e.id))

            # ActionHistory レコードを作成
            ActionHistory.objects.create(
                entity=next_entity,
                acted_at_turn=i,
                done=False,
            )

            # シミュレーションの結果を保存
            simulation.append(
                EntityVO(name=next_entity.name, next_turn=next_entity.next_turn)
            )

            # 次の行動予定を仮で更新
            next_entity.next_turn += (
                TurnManagementService.calculate_next_turn_increment(next_entity.speed)
            )

        return simulation
