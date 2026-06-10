import os

from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RokunoheMinutesRagService(BaseChatService):
    model_name = ModelName.GPT_5_MINI
    collection_name = "rokunohe_minutes"

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        rag_service = OpenAILlmRagService(
            model=self.config.model,
            api_key=self.config.api_key,
            collection_name=self.collection_name,
        )
        # 既にインデックス済みであることを前提とする
        response_dict = rag_service.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response_dict["answer"],
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
