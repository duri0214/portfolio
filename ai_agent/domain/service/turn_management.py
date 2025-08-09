from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.valueobject.turn_management import EntityVO
from ai_agent.models import ActionHistory, Message
from lib.log_service import LogService

log_service = LogService("turn_management_service.log")


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

    @staticmethod
    def reset_timeline():
        """
        タイムラインをリセットし、新しい会話の準備をします。

        以下の処理を実行します：
        1. すべてのメッセージ履歴を削除
        2. すべてのActionHistory（行動履歴）レコードを削除
        3. 各エンティティのActionTimelineを初期化（speed属性に基づいて）
        4. 次の10ターン分のアクションをシミュレーションしてActionHistoryに登録
        5. すべてのActionHistoryレコードを未完了状態（done=False）に設定

        この処理により、エンティティのスピード属性に基づいた新しい行動順序が決定されます。
        """
        # メッセージ履歴をクリア
        Message.objects.all().delete()
        log_service.write("All messages have been cleared.")

        # ActionHistoryをクリア
        ActionHistory.objects.all().delete()
        log_service.write("All ActionHistory records have been cleared.")

        # タイムラインを初期化
        TurnManagementService.initialize_timeline()

        # 未来の10ターン分をActionHistoryに登録
        TurnManagementService.simulate_next_actions(max_steps=10)

        # ActionHistoryのすべての行動を未完了（done=False）にする
        ActionHistory.objects.all().update(done=False)

    @staticmethod
    def progress_turn(action_history: ActionHistory) -> str:
        """
        現在のアクション履歴に基づいてエンティティの応答を生成し、
        ターンを進行させるメソッド。

        処理の流れ：
        1. エンティティの応答生成
        2. 生成された応答をメッセージとして保存
        3. 現在のアクションを完了状態にマーク

        Args:
            action_history (ActionHistory): 現在のアクション履歴（エンティティ情報を含む）

        Returns:
            str: 生成された応答テキスト（エラーの場合はエラーメッセージ）
        """
        from ai_agent.domain.service.context_analyzer import ContextAnalyzerService
        from ai_agent.domain.service.input_processor import InputProcessor

        # 1. エンティティ情報を取得し、最新の会話コンテキストを取得
        entity = action_history.entity
        context = TurnManagementRepository.get_recent_chat_messages()

        # 2. チャット履歴をエンティティの専門性に合わせてリフレーミング
        try:
            reframed_context = ContextAnalyzerService.reframe_context_for_entity(
                context=context, entity=entity
            )
        except ValueError:
            reframed_context = context

        # 3. ガードレールを適用して応答を生成・保存
        processor = InputProcessor(entity)
        response_text = processor.process_input(reframed_context)
        TurnManagementRepository.create_message(
            content=response_text, action_history=action_history
        )

        # 4. 生成された最新のメッセージ内容を返却
        latest_message = TurnManagementRepository.get_latest_chat_message()
        response_text = latest_message.message_content if latest_message else ""

        return response_text
