import os

from ai_agent.domain.repository.response_generator import ResponseGeneratorRepository
from ai_agent.models import Entity
from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig


class ContextAnalyzerService:
    """会話コンテキストを分析するサービスクラス

    このサービスはチャットコンテキストを分析し、エンティティの専門領域に合わせて
    リフレーミングします。
    """

    @classmethod
    def _extract_keywords_from_rag(
        cls, thinking_type: str, thinking_type_disp: str
    ) -> str:
        """エンティティの思考タイプに関連するRAG素材から重要なキーワードを抽出する

        Args:
            thinking_type (str): エンティティの思考タイプ (material_typeと一致)
            thinking_type_disp (str): エンティティの思考タイプの表示名

        Returns:
            str: 抽出されたキーワード（カンマ区切り）
        """
        # エンティティの思考タイプからRAG素材を取得
        rag_source = ResponseGeneratorRepository.get_rag_source_merged(thinking_type)
        if not rag_source:
            return ""

        config = OpenAIGptConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=500,  # キーワード抽出には少ないトークン数で十分
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        llm_service = LlmCompletionService(config)
        try:
            extraction_response = llm_service.retrieve_answer(
                chat_history=[
                    Message(
                        role=RoleType.SYSTEM,
                        content="あなたは文章から重要なキーワードを抽出する専門家です。",
                    ),
                    Message(
                        role=RoleType.USER,
                        content=f"次の文章から{thinking_type_disp}に関連する重要なキーワードを10-15個抽出してください。キーワードのみをカンマ区切りで返してください。\n\n{rag_source}",
                    ),
                ]
            )
            keywords = extraction_response.choices[0].message.content.strip()
            return f"{thinking_type_disp}に関連する重要キーワード: {keywords}"
        except Exception as e:
            print(f"キーワード抽出中にエラーが発生: {e}")
            return ""

    @classmethod
    def reframe_context_for_entity(cls, context: str, entity: Entity) -> str:
        """チャット履歴をエンティティの専門領域に合わせてリフレーミングします

        処理の流れ：
        1. リフレーミングのためのOpenAI設定を初期化
        2. エンティティの専門分野に基づいたシステムプロンプトを構築
        3. エンティティの思考タイプに関連するRAG素材から重要キーワードを抽出
        4. ユーザープロンプトを構築し、LLMによるリフレーミングを実行
        5. リフレーミング結果を返却（エラー時は元のコンテキストを返却）

        Args:
            context (str): リフレーミング対象のチャット履歴
            entity (Entity): リフレーミングを適用するエンティティ

        Returns:
            str: エンティティの専門領域に合わせてリフレーミングされたコンテキスト。
                 LLMアクセスに失敗した場合は元のコンテキストをそのまま返します。
        """
        # 1. リフレーミングのためのOpenAI設定を初期化
        config = OpenAIGptConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        llm_service = LlmCompletionService(config)

        # 2. エンティティの専門分野に基づいたシステムプロンプトを構築
        thinking_type = entity.thinking_type
        thinking_type_disp = entity.get_thinking_type_display() or thinking_type
        system_prompt = f"""
        あなたは専門分野に特化したAIアシスタントです。会話の内容を{entity.name}の専門分野に合わせて解釈し直してください。
        {entity.name}の専門分野は {thinking_type_disp} です。
        次の会話コンテキストを、{thinking_type_disp} の観点から解釈し、専門的な視点を反映させた形に変換してください。
        元の文脈を維持しながらも、専門的な要素や関連性を強調し、その分野の専門家が考えるような形に書き換えてください。
        """

        # 3. エンティティの思考タイプに関連するRAG素材から重要キーワードを抽出
        rag_keywords = ""
        if thinking_type:
            rag_keywords = cls._extract_keywords_from_rag(
                thinking_type, thinking_type_disp
            )

        # 4. ユーザープロンプトを構築し、LLMによるリフレーミングを実行
        user_prompt = f"以下の会話を、{thinking_type_disp} の専門家の視点でリフレーミングしてください: 会話コンテキスト: {context}\n\n{rag_keywords}"

        try:
            response = llm_service.retrieve_answer(
                chat_history=[
                    Message(role=RoleType.SYSTEM, content=system_prompt),
                    Message(role=RoleType.USER, content=user_prompt),
                ]
            )
            # 5. リフレーミング結果を返却（エラー時は元のコンテキストを返却）
            reframed_context = response.choices[0].message.content.strip()
            return reframed_context
        except Exception as e:
            print(f"コンテキストリフレーミング中にエラーが発生: {e}")
            return context
