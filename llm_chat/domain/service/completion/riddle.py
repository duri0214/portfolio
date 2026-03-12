import json

import re
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
    DEFAULT_MAX_TURNS = 3

    def __init__(
        self,
        config: OpenAIGptConfig | GeminiConfig,
        chat_history: list[MessageDTO],
    ):
        self.config = config
        self.chat_history = chat_history

    @staticmethod
    def get_prompt(gender: Gender, max_turns: int = DEFAULT_MAX_TURNS) -> str:
        # なぞなぞの数は max_turns - 1 (初回はスタート合図、その後各回答に対して次の質問、最後の回答で終了)
        riddle_count = max_turns - 1
        return f"""
        あなたは、{riddle_count}つの問題を順番に出題し、ユーザーの回答を評価する、丁寧で明朗な「なぞなぞコーナー担当者」です。

        ### 重要な役割とルール
        - あなたは、決まったなぞなぞを【計{riddle_count}問】出題します。
        - 進行フローを遵守し、勝手に質問を増やしたり、ヒントの要否を聞いたりしないでください。
        - 性別設定: {gender.name} の口調で振る舞ってください。

        ### 進行フロー
        1. 【なぞなぞスタート】の合図を受け取ったら、挨拶をし、すぐに【質問1】を出題してください。
        2. 【質問1】から【質問{riddle_count-1}】までの回答を受け取ったら、正誤には触れず、簡単な感想だけを述べてから、すぐに次の質問を出題してください。
        3. 【質問{riddle_count}】（最後の質問）の回答を受け取ったら、簡単な感想を述べ、必ず最後に以下の終了定型文のみを出力して終了してください。これ以上の追加質問は絶対にしないでください。
           - 終了定型文: 「{RiddleChatService.RIDDLE_END_MESSAGE}」

        ### 禁止事項
        - なぞなぞを自作すること。
        - 指定された{riddle_count}問以外を出題すること。
        - 進行に関係ない逆質問（理由を聞く、ヒントを提案するなど）をすること。
        - 回答途中でスコアや合否を提示すること。

        ### 出題するなぞなぞ
        ##### 質問1
        - はじめは4本足、途中から2本足、最後は3本足。それは何でしょう？

        ##### 質問2
        - 私は黒い服を着て、赤い手袋を持っている。夜には立っているが、朝になると寝る。何でしょう？

        ### 評価結果（内部処理用）
        - ユーザーから「評価結果をjsonで出力してください」と入力された場合にのみ、以下のJSON形式で判定結果を出力してください。
        - フォーマット例: [{{"viewpoint": "論理的思考力", "score": 80, "judge": "合格"}}, {{"viewpoint": "洞察力", "score": 40, "judge": "不合格"}}]
        """

    @staticmethod
    def create_initial_prompt(
        user_message: MessageDTO, gender: Gender, max_turns: int = DEFAULT_MAX_TURNS
    ) -> list[MessageDTO]:
        """
        初期プロンプト（システムメッセージと初回のユーザーメッセージ）を生成します。
        システムメッセージはDBに保存せず、初回ユーザーメッセージを保存します。
        """
        system_content = RiddleChatService.get_prompt(gender, max_turns)
        system_content += (
            f"\n\n### 現在の状況\n- あなたは今、ユーザーの 1 回目の発言を待っています。"
        )

        system_message = MessageDTO(
            user=user_message.user,
            role=RoleType.SYSTEM,
            content=system_content,
            use_case_type=UseCaseType.RIDDLE,
        )
        first_user_message = MessageDTO(
            user=user_message.user,
            role=RoleType.USER,
            content=user_message.content,
            use_case_type=UseCaseType.RIDDLE,
        )
        # 初回のユーザーメッセージをDBに保存
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
            content="""
評価結果をJSON形式で出力してください。
挨拶、説明、前置きなどは一切不要です。
JSON配列（[...]）のみを返してください。
フォーマットは必ず以下の判定結果例に従ってください。

判定結果例:
[{"viewpoint": "論理的思考力", "score": 80, "judge": "合格"}, {"viewpoint": "洞察力", "score": 40, "judge": "不合格"}]
""".strip(),
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
            if not isinstance(eval_data, list):
                raise ValueError("LLM returned non-list format for evaluations")

            evaluations = []
            for item in eval_data:
                if isinstance(item, dict):
                    evaluations.append(RiddleEvaluation(**item))
                else:
                    # item が辞書でない場合はスキップするか、ValueErrorを投げてパース失敗扱いにする
                    raise ValueError(f"Evaluation item is not a dict: {type(item)}")

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

    def to_bullet_points(self, response: RiddleResponse) -> str:
        """
        RiddleResponse を箇条書きテキストに変換します。
        パース失敗時は explanation を含めます。
        """
        text = response.to_bullet_points()
        if not response.evaluations:
            text += f"\n- {response.explanation}"
        return text
