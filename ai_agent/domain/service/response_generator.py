from ai_agent.domain.repository.response_generator import ResponseGeneratorRepository
from ai_agent.domain.repository.turn_management import TurnManagementRepository
from ai_agent.domain.service.context_analyzer import ContextAnalyzerService
from ai_agent.domain.service.input_processor import InputProcessor
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
        2. RAG素材を使用してチャット履歴をエンティティの専門性に合わせてリフレーミング
        3. ガードレールを適用して応答を生成・保存
        4. 生成された最新のメッセージ内容を返却

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
        context = ResponseGeneratorRepository.get_recent_chat_messages()

        # 2. チャット履歴をエンティティの専門性に合わせてリフレーミング
        reframed_context = ContextAnalyzerService.reframe_context_for_entity(
            context=context, entity=entity
        )

        # 3. ガードレールを適用して応答を生成・保存
        processor = InputProcessor(entity)
        response_text = processor.process_input(reframed_context)
        TurnManagementRepository.create_message(
            content=response_text, action_history=action_history
        )

        # 4. 生成された最新のメッセージ内容を返却
        latest_message = ResponseGeneratorRepository.get_latest_chat_message()
        response_text = latest_message.message_content if latest_message else ""

        return response_text
