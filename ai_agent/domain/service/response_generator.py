from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.thinking_engine_processor import ThinkingEngineProcessor
from ai_agent.domain.service.turn_management import TurnManagementService
from ai_agent.models import ActionHistory
from lib.log_service import LogService

log_service = LogService("response_generator.log")


class ResponseGenerator:
    """エンティティの応答を生成するファサードクラス

    このクラスは、アクション履歴とコンテキストを使用して、
    ガードレールを適用し、エンティティの応答を生成するためのファサードを提供します。
    """

    @staticmethod
    def generate_response(action_history: ActionHistory) -> str:
        """エンティティの応答を生成する

        処理の流れ：
        1. エンティティ情報を取得し、最新の会話コンテキストを取得
        2. エンティティのアクションタイムラインを確認し、存在しない場合はエラー
        3. エンティティが現在の会話内容に対応できるかチェック
        4. ThinkingEngineProcessorを使用して応答を生成・保存
        5. 生成された最新のメッセージ内容を返却

        Args:
            action_history (ActionHistory): 現在のアクション履歴（エンティティ情報を含む）

        Returns:
            str: 生成された応答テキスト（エラーの場合はエラーメッセージ）
        """
        # 1. エンティティ情報を取得し、最新の会話コンテキストを取得
        entity = action_history.entity
        context = ThinkingEngineProcessor.get_recent_context()

        # 2. エンティティのアクションタイムラインを確認し、存在しない場合はエラー
        active_entity_timeline = TurnManagementRepository.get_action_timeline(entity)
        if not active_entity_timeline:
            error_message = f"重大なエラー: {entity.name}のアクションタイムラインが見つかりません。システム管理者に連絡してください。"
            log_service.write(
                f"DATA INCONSISTENCY ERROR: Entity {entity.id}:{entity.name} has ActionHistory but no ActionTimeline"
            )
            return error_message

        # 3. エンティティが現在の会話内容に対応できるかチェック
        can_act = TurnManagementService.can_respond_to_input(entity, context)
        active_entity_timeline.can_act = can_act
        active_entity_timeline.save()
        if not can_act:
            thinking_type_disp = entity.get_thinking_type_display()
            error_message = f"[ERROR]{entity.name}（{thinking_type_disp}）はチャットに参加できませんでした"
            TurnManagementRepository.create_message(
                content=error_message, action_history=action_history
            )
            return error_message

        # 4. ThinkingEngineProcessorを使用して応答を生成・保存
        processor = ThinkingEngineProcessor()
        processor.apply_guardrail_and_generate_response(
            action_history=action_history, context=context
        )

        # 5. 生成された最新のメッセージ内容を返却
        response_text = ThinkingEngineProcessor.get_recent_context(limit=1)

        return response_text
