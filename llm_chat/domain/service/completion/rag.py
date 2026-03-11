import os
from pathlib import Path

from config.settings import BASE_DIR
from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from lib.llm.valueobject.rag import PdfDataloader
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIRagChatService(BaseChatService):
    model_name = ModelName.GPT_5_MINI

    def __init__(self):
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        # Step1: User の質問を保存
        ChatLogRepository.insert(user_message)

        # Step2: 回答を取得
        file_path = (
            Path(BASE_DIR)
            / "lib/llm/pdf_sample/令和4年版少子化社会対策白書全体版（PDF版）.pdf"
        )
        dataloader = PdfDataloader(str(file_path))
        rag_service = OpenAILlmRagService(
            model=self.config.model,
            api_key=self.config.api_key,
        )
        rag_service.upsert_documents(dataloader.data)
        response_dict = rag_service.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response_dict["answer"],
            use_case_type=UseCaseType.OPENAI_GPT,
        )
