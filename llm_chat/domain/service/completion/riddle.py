import json

from django.contrib.auth.models import User

from lib.llm.service.completion import LlmCompletionService, BaseLLMTask
from lib.llm.valueobject.completion import RoleType, Message
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    RiddleResponse,
    RiddleEvaluation,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RiddleChatService(BaseLLMTask):
    """
    なぞなぞの評価タスク。
    LLMからの評価結果（JSON）をパースし、RiddleResponse型で返します。
    """

    RIDDLE_END_MESSAGE = "本日はなぞなぞにご参加いただき、ありがとうございました。"

    def __init__(
        self,
        config: OpenAIGptConfig | GeminiConfig,
        chat_history: list[MessageDTO],
    ):
        self.config = config
        self.chat_history = chat_history

    @staticmethod
    def get_prompt(gender: Gender) -> str:
        return f"""
        あなたはなぞなぞコーナーの担当者です。

        #制約条件
        - あなた自身で新しいなぞなぞを考えてはいけません。必ず以下の「##### 質問1」と「##### 質問2」を順番に出題してください。
        - 「なぞなぞスタート」または開始の合図をされたら、まずあいさつをし、続けて

        ##### 質問1
        を出題してください。
        - ユーザーが質問1に回答したら、その正誤には触れず、すぐに

        ##### 質問2
        を出題してください。
        - 質問2の回答を受け取ったら、感想を述べるとともに「{RiddleChatService.RIDDLE_END_MESSAGE}」と言って終了してください。
        - 判定結果（スコアや合否）は会話中に出力してはいけません。
        - {gender.name} の口調で会話を行ってください。
        - 「評価結果をjsonで出力してください」と入力された場合にのみ、指定のフォーマットで判定結果を出力してください。

        ##### 質問1
        - はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？

        ##### 質問2
        - 私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？

        #判定結果例
        [{{"viewpoint": "論理的思考力", "score": 50, "judge": "不合格"}},{{"viewpoint": "洞察力", "score": 96, "judge": "合格"}}]
    """

    @staticmethod
    def create_initial_prompt(user_message: MessageDTO, gender: Gender) -> list[MessageDTO]:
        """
        初期プロンプト（システムメッセージと初回のユーザーメッセージ）を生成します。
        システムメッセージはDBに保存せず、初回ユーザーメッセージのみ保存します。
        """
        system_message = MessageDTO(
            user=user_message.user,
            role=RoleType.SYSTEM,
            content=RiddleChatService.get_prompt(gender),
            use_case_type=UseCaseType.RIDDLE,
        )
        first_user_message = MessageDTO(
            user=user_message.user,
            role=RoleType.USER,
            content=user_message.content,
            use_case_type=UseCaseType.RIDDLE,
        )
        # ユーザーメッセージのみDBに保存
        ChatLogRepository.insert(first_user_message)

        # システムメッセージを先頭に含めて返す
        return [system_message, first_user_message]

    def execute(self, login_user: User) -> RiddleResponse:
        """
        評価プロンプトを送信し、結果を RiddleResponse に変換します。
        """
        # 評価用のユーザーメッセージ（非表示）
        eval_message = Message(
            role=RoleType.USER,
            content="評価結果をjsonで出力してください。フォーマットは判定結果例に従うこと",
        )

        # メッセージ履歴を準備
        messages = [x.to_message() for x in self.chat_history]
        messages.append(eval_message)

        # LLM実行
        chat_result = LlmCompletionService(self.config).retrieve_answer(messages)
        raw_content = chat_result.answer

        # パース処理
        try:
            # LLMが ```json ... ``` で囲んでくる場合を考慮
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```"):
                lines = cleaned_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                cleaned_content = "\n".join(lines).strip()

            eval_data = json.loads(cleaned_content)
            # eval_data はリスト形式 [{...}, {...}] と想定
            evaluations = [RiddleEvaluation(**item) for item in eval_data]

            return RiddleResponse(
                answer=raw_content,
                evaluations=evaluations,
                explanation="なぞなぞの評価結果です。",
            )
        except (json.JSONDecodeError, ValueError) as e:
            # パース失敗時のフォールバックまたはエラーハンドリング
            # ここで「残心」を持ってエラーを処理
            return RiddleResponse(
                answer=raw_content,
                evaluations=[],
                explanation=f"評価結果のパースに失敗しました: {str(e)}",
            )
