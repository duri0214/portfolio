import json
import re

from django.contrib.auth.models import User

from lib.llm.service.completion import LlmCompletionService, BaseLLMTask
from lib.llm.valueobject.completion import RoleType, Message
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.repository.completion.riddle import RiddleQuestionRepository
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    RiddleResponse,
    RiddleEvaluation,
    Riddle,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RiddleChatService(BaseLLMTask):
    """
    なぞなぞセッション専用のLLM対話サービス。

    LLMへのプロンプト生成、メッセージの生成、およびセッション終了後の
    最終評価（JSONパースと構造化）を担当します。

    Attributes:
        config (OpenAIGptConfig | GeminiConfig): LLMの設定。
        chat_history (list[MessageDTO]): セッションの会話履歴。
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
    def get_riddle_set(max_turns: int | None = None) -> list[Riddle]:
        """
        DBからなぞなぞの問題セットを取得します。
        """
        riddle_set = RiddleQuestionRepository.fetch_all()
        if not riddle_set:
            raise ValueError(
                "なぞなぞの問題が登録されていません。管理画面から問題を登録してください。"
            )
        if max_turns is not None:
            riddle_set = riddle_set[: max_turns - 1]
        return riddle_set

    @staticmethod
    def is_session_finished(
        user: User,
        assistant_message: MessageDTO,
        riddle_count: int,
        start_signals: list[str],
    ) -> bool:
        """
        セッションが終了したかどうかを判定します。
        """
        chat_history = ChatLogRepository.find_chat_history(user)
        answer_turns = [
            m
            for m in chat_history
            if m.role == RoleType.USER
            and not any(sig in m.content for sig in start_signals)
        ]
        return (
            len(answer_turns) >= riddle_count
            or RiddleChatService.RIDDLE_END_MESSAGE in assistant_message.content
        )

    @staticmethod
    def finalize_message(
        assistant_message: MessageDTO,
        riddle_count: int,
        chat_service: BaseChatService,
        user: User,
        riddle_set: list[Riddle],
    ) -> None:
        """
        メッセージのクリーニングと評価結果の付与を行います。
        """
        # 終了メッセージのクリーニング
        next_riddle_num = riddle_count + 1
        extra_patterns = [
            rf"(?:(?:それでは|では)?(?:次の|第|第 )?問題です。?|質問{next_riddle_num}[:：]?|第{next_riddle_num}問[:：]?|問{next_riddle_num}[:：]?|問題{next_riddle_num}[:：]?)",
            r"続けて別のなぞなぞを出しましょうか？",
            r"このまま答えをたくさん出しますか？",
            r"別のなぞなぞを楽しみますか？",
            r"もっと続けますか？",
        ]
        combined_pattern = "|".join(extra_patterns)
        if re.search(combined_pattern, assistant_message.content):
            end_msg = RiddleChatService.RIDDLE_END_MESSAGE
            if end_msg in assistant_message.content:
                parts = assistant_message.content.split(end_msg)
                main_content = re.split(combined_pattern, parts[0])[0].strip()
                # 余計な見出し（#####）が残っている場合を削除
                main_content = re.sub(r"#####\s*$", "", main_content).strip()
                assistant_message.content = main_content.rstrip() + "\n\n" + end_msg

        # 評価の実行と追記
        chat_service.chat_history.append(assistant_message)
        evaluation_text = chat_service.evaluate(login_user=user, riddle_set=riddle_set)
        assistant_message.content += f"\n\n{evaluation_text}"
        assistant_message.content = assistant_message.content.strip()

    @staticmethod
    def get_prompt(
        gender: Gender,
        riddle_set: list[Riddle],
        current_index: int | None = None,
    ) -> str:
        riddle_count = len(riddle_set)
        riddle_list_str = ""
        for i, item in enumerate(riddle_set):
            riddle_list_str += f"##### 質問{i+1}\n- {item.question}\n\n"

        status_str = ""
        if current_index is not None:
            if current_index < riddle_count:
                status_str = f"現在は【質問{current_index + 1}】を出題する番、またはその回答を待っている状態です。"
            else:
                status_str = "全問出題済みです。終了処理を行ってください。"

        return f"""
        あなたは、{riddle_count}つの問題を順番に出題し、ユーザーの回答を評価する、丁寧で明朗な「なぞなぞコーナー担当者」です。

        ### 重要な役割とルール
        - あなたは、決まったなぞなぞを【計{riddle_count}問】出題します。
        - 進行フローを遵守し、勝手に質問を増やしたり、ヒントの要否を聞いたりしないでください。
        - ユーザーから、現在出題している問題の内容について質問や確認があった場合は、優しくその問題の内容を再提示し、回答を促してください。
        - 回答が得られるまでは、次の問題に進まないでください。
        - 性別設定: {gender.name} の口調で振る舞ってください。
        - **Markdown 形式で読みやすく出力してください。特に、感想と次の質問の間には必ず 2 つの改行（空行）を挿入してください。**
        - **回答の冒頭に挨拶や「回答ありがとうございます」などの一文を入れる場合、その直後に必ず 2 つの改行（空行）を挿入してから「##### 質問n」を開始してください。**

        ### 進行フロー
        1. 【なぞなぞスタート】の合図を受け取ったら、挨拶をし、すぐに【質問1】を出題してください。
        2. 【質問1】から【質問{riddle_count-1}】までの回答を受け取ったら、正誤には触れず、簡単な感想だけを述べてから、すぐに次の質問を出題してください。
        3. 【質問{riddle_count}】（最後の質問）の回答を受け取ったら、簡単な感想を述べ、必ず最後に以下の終了定型文のみを出力して終了してください。これ以上の追加質問や、会話を継続するような提案（「別のなぞなぞを出しましょうか？」など）は絶対にしないでください。
           - 終了定型文: 「{RiddleChatService.RIDDLE_END_MESSAGE}」

        ### 禁止事項
        - なぞなぞを自作すること。
        - 指定された{riddle_count}問以外を出題すること。
        - 進行に関係ない逆質問（理由を聞く、ヒントを提案するなど）をすること。
        - 回答途中でスコアや合否を提示すること。

        ### 出題するなぞなぞ
        {riddle_list_str}

        ### 現在の状況
        - {status_str}

        ### 評価結果（内部処理用）
        - ユーザーから「評価結果をjsonで出力してください」と入力された場合にのみ、以下のJSON形式で判定結果を出力してください。
        - フォーマット例: [{{"viewpoint": "論理的思考力", "score": 80, "judge": "合格"}}, {{"viewpoint": "洞察力", "score": 40, "judge": "不合格"}}]
        """

    @staticmethod
    def create_initial_prompt(
        user_message: MessageDTO,
        gender: Gender,
        riddle_set: list[Riddle],
    ) -> list[MessageDTO]:
        """
        初期プロンプト（システムメッセージと初回のユーザーメッセージ）を生成します。
        システムメッセージはDBに保存せず、初回ユーザーメッセージを保存します。
        """
        system_content = RiddleChatService.get_prompt(
            gender=gender, riddle_set=riddle_set, current_index=0
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

    def execute(self, login_user: User, riddle_set: list[Riddle]) -> RiddleResponse:
        """
        評価プロンプトを送信し、結果を RiddleResponse に変換します。
        """
        riddle_qa_str = ""
        for i, item in enumerate(riddle_set):
            riddle_qa_str += f"問{i+1}: {item.question}\n正解: {item.answer}\n\n"

        # 評価用のユーザーメッセージ（非表示）
        eval_message = Message(
            role=RoleType.USER,
            content=f"""
以下のなぞなぞの正解データを参考に、ユーザーの回答を多角的に評価し、JSON形式で出力してください。

### なぞなぞの正解データ
{riddle_qa_str}

### 評価の指示
- 挨拶、説明、前置きなどは一切不要です。
- JSONオブジェクト（{{...}}）のみを返してください。
- フォーマットは必ず以下のJSON構造に従ってください。

JSON構造:
{{
  "correctness": 3,
  "reasoning": 4,
  "creativity": 2,
  "rebuttal": 0,
  "comment": "コメント"
}}
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
            # eval_data は辞書形式 {...} と想定
            if not isinstance(eval_data, dict):
                raise ValueError("LLM returned non-dict format for evaluation")

            evaluation = RiddleEvaluation(**eval_data)

            return RiddleResponse(
                answer=raw_content,
                evaluation=evaluation,
                explanation="なぞなぞの評価結果です。",
            )
        except (json.JSONDecodeError, ValueError) as e:
            # パース失敗時のフォールバックまたはエラーハンドリング
            return RiddleResponse(
                answer=raw_content,
                evaluation=None,
                explanation=f"評価結果のパースに失敗しました: {str(e)}",
            )

    @staticmethod
    def to_bullet_points(response: RiddleResponse) -> str:
        """
        RiddleResponse を箇条書きテキストに変換します。
        パース失敗時は explanation を含めます。
        """
        text = response.to_bullet_points()
        if not response.evaluation:
            text += f"\n- {response.explanation}"
        return text
