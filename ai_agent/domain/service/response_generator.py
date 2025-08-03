from ai_agent.domain.repository.thinking_engine_processor import (
    ThinkingEngineProcessorRepository,
)
from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.context_analyzer import ContextAnalyzerService
from ai_agent.domain.service.thinking_engine_processor import ThinkingEngineProcessor
from ai_agent.domain.service.thinking_engines.cloud_act_pdf import CloudActPdfService
from ai_agent.domain.service.thinking_engines.declining_birth_rate_pdf import (
    DecliningBirthRatePdfService,
)
from ai_agent.domain.service.thinking_engines.googlemaps_review import (
    GoogleMapsReviewService,
)
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
           - エンティティのthinking_typeに基づいて適切な思考エンジンサービスを選択
           - RAG素材を使用してチャット履歴をエンティティの専門性に合わせてリフレーミング
           - リフレーミングされたコンテキストが応答可能かどうかを評価（True/False）
        4. ThinkingEngineProcessorを使用して応答を生成・保存
        5. 生成された最新のメッセージ内容を返却

        サポートされている思考エンジン：
        - GoogleMapsReviewService: 地図・レビュー関連の質問に対応
        - CloudActPdfService: 法律文書・クラウド関連の質問に対応
        - DecliningBirthRatePdfService: 少子化・人口動態関連の質問に対応

        Args:
            action_history (ActionHistory): 現在のアクション履歴（エンティティ情報を含む）

        Returns:
            str: 生成された応答テキスト（エラーの場合はエラーメッセージ）
        """
        # 1. エンティティ情報を取得し、最新の会話コンテキストを取得
        entity = action_history.entity
        context = ThinkingEngineProcessorRepository.get_recent_messages()

        # 2. エンティティのアクションタイムラインを確認し、存在しない場合はエラー
        active_entity_timeline = TurnManagementRepository.get_action_timeline(entity)
        if not active_entity_timeline:
            error_message = f"重大なエラー: {entity.name}のアクションタイムラインが見つかりません。システム管理者に連絡してください。"
            log_service.write(
                f"DATA INCONSISTENCY ERROR: Entity {entity.id}:{entity.name} has ActionHistory but no ActionTimeline"
            )
            return error_message

        # 3. エンティティが現在の会話内容に対応できるかチェック
        can_act = True

        # エンティティのthinking_typeに基づいて適切な思考エンジンサービスを選択
        if entity.thinking_type == "google_maps_based":
            # RAG素材を使用してチャット履歴をエンティティの専門性に合わせてリフレーミング
            service = GoogleMapsReviewService()
            reframed_context = ContextAnalyzerService.reframe_context_for_entity(
                context=context,
                entity=entity,
                rag_source=service.get_contents_merged(),
            )
            # リフレーミングされたコンテキストが応答可能かどうかを評価（True/False）
            can_act = service.can_respond(reframed_context, entity)

        elif entity.thinking_type == "cloud_act_based":
            service = CloudActPdfService()
            reframed_context = ContextAnalyzerService.reframe_context_for_entity(
                context=context,
                entity=entity,
                rag_source=service.get_contents_merged(),
            )
            can_act = service.can_respond(reframed_context, entity)

        elif entity.thinking_type == "declining_birth_rate_based":
            service = DecliningBirthRatePdfService()
            reframed_context = ContextAnalyzerService.reframe_context_for_entity(
                context=context,
                entity=entity,
                rag_source=service.get_contents_merged(),
            )
            can_act = service.can_respond(reframed_context, entity)

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
        latest_message = ThinkingEngineProcessorRepository.get_latest_message()
        response_text = latest_message.message_content if latest_message else ""

        return response_text
