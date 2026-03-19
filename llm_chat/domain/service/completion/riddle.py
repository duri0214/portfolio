import json
import re

from django.contrib.auth.models import User

from lib.llm.service.completion import LlmCompletionService, BaseLLMTask
from lib.llm.valueobject.completion import RoleType, Message
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.repository.completion.riddle import RiddleQuestionRepository
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import (
    Gender,
    RiddleResponse,
    RiddleEvaluation,
    RiddleTurnEvaluation,
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
            riddle_set = riddle_set[:max_turns]
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
    def report(
        content: str,
        riddle_count: int,
        user: User,
    ) -> str:
        """
        メッセージのクリーニングと終了メッセージの付与、評価結果の追記を行います。

        アシスタントが生成したメッセージから不要なパターン（「次の質問です」など）を削除し、
        セッション終了の定型文およびユーザーの回答に対する最終的な評価結果を追記します。
        このメソッドは SessionState.FINISHED 状態に対応する処理を担います。

        Args:
            content (str): クリーニング対象のメッセージ本文。
            riddle_count (int): 現在のセッションでの回答数。
            user (User): 評価対象のユーザー。

        Returns:
            str: クリーニングおよび評価結果が追記されたメッセージ本文。
        """
        # 1. 不要なパターンのクリーニング
        next_riddle_num = riddle_count + 1
        extra_patterns = [
            rf"(?:(?:それでは|では)?(?:次の|第|第 )?問題です。?|質問{next_riddle_num}[:：]?|第{next_riddle_num}問[:：]?|問{next_riddle_num}[:：]?|問題{next_riddle_num}[:：]?)",
            r"続けて別のなぞなぞを出しましょうか？",
            r"このまま答えをたくさん出しますか？",
            r"別のなぞなぞを楽しみますか？",
            r"もっと続けますか？",
        ]
        combined_pattern = "|".join(extra_patterns)
        content = re.split(combined_pattern, content)[0].strip()
        # 余計な見出し（#####）が残っている場合を削除
        content = re.sub(r"#####\s*$", "", content).strip()

        # 2. 終了メッセージ（定型文）の付与
        end_msg = RiddleChatService.RIDDLE_END_MESSAGE
        if end_msg not in content:
            content = content.rstrip() + "\n\n" + end_msg

        # 3. 最終レポートの追記
        report_text = RiddleChatService.build_profile_report(user=user)
        content += f"\n\n{report_text}"
        return content.strip()

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
        # このメソッドを呼び出す際は、UseCaseType に拘わらずなぞなぞモード（RIDDLE）として振る舞うよう強制する
        user_message.use_case_type = UseCaseType.RIDDLE

        # システムメッセージを先頭に含めて返す
        return [system_message, user_message]

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
        - 各スコアは 0-5 の整数で返してください。
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

    @staticmethod
    def _clean_json_text(raw_content: str) -> str:
        cleaned_content = raw_content.strip()
        if cleaned_content.startswith("```"):
            lines = cleaned_content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned_content = "\n".join(lines).strip()
        return cleaned_content

    @staticmethod
    def _extract_json_object(raw_content: str) -> str | None:
        match = re.search(r"\{.*}", raw_content, re.DOTALL)
        if not match:
            return None
        return match.group(0).strip()

    @staticmethod
    def _parse_json_dict(raw_content: str) -> dict:
        cleaned_content = RiddleChatService._clean_json_text(raw_content)
        try:
            eval_data = json.loads(cleaned_content)
        except json.JSONDecodeError:
            extracted = RiddleChatService._extract_json_object(cleaned_content)
            if not extracted:
                extracted = RiddleChatService._extract_json_object(raw_content)
            if not extracted:
                raise
            eval_data = json.loads(extracted)
        if not isinstance(eval_data, dict):
            raise ValueError("LLM returned non-dict format for evaluation")
        return eval_data

    @staticmethod
    def _normalize_answer(text: str) -> str:
        return re.sub(r"\s+", "", (text or "")).lower()

    @staticmethod
    def _fallback_turn_evaluation(answer: str, user_answer: str) -> RiddleTurnEvaluation:
        answer_norm = RiddleChatService._normalize_answer(answer)
        user_norm = RiddleChatService._normalize_answer(user_answer)
        is_correct = bool(answer_norm) and (
            answer_norm in user_norm or user_norm in answer_norm
        )
        correctness = 5 if is_correct else 0
        return RiddleTurnEvaluation(
            correctness=correctness,
            reasoning=0,
            creativity=0,
            rebuttal=0,
        )

    @staticmethod
    def evaluate_turn(
        config: OpenAIGptConfig | GeminiConfig,
        question: str,
        answer: str,
        user_answer: str,
    ) -> RiddleTurnEvaluation | None:
        """
        単問の評価をLLMで算出し、数値スコアを返します。
        """
        eval_message = Message(
            role=RoleType.USER,
            content=f"""
以下のなぞなぞについて、ユーザー回答を多角的に評価し、JSON形式で出力してください。

### なぞなぞ
問題: {question}
正解: {answer}
ユーザー回答: {user_answer}

        ### 評価の指示
        - 挨拶、説明、前置きなどは一切不要です。
        - JSONオブジェクト（{{...}}）のみを返してください。
        - 各スコアは 0-5 の整数で返してください。
        - フォーマットは必ず以下のJSON構造に従ってください。

JSON構造:
{{
  "correctness": 3,
  "reasoning": 4,
  "creativity": 2,
  "rebuttal": 0
}}
""".strip(),
        )

        chat_result = LlmCompletionService(config).retrieve_answer([eval_message])
        raw_content = chat_result.answer

        try:
            eval_data = RiddleChatService._parse_json_dict(raw_content)
            return RiddleTurnEvaluation(**eval_data)
        except (json.JSONDecodeError, ValueError):
            return RiddleChatService._fallback_turn_evaluation(answer, user_answer)

    @staticmethod
    def format_turn_scores(evaluation: RiddleTurnEvaluation) -> str:
        return (
            f"正確性: {evaluation.correctness}｜"
            f"論理性: {evaluation.reasoning}｜"
            f"独創性: {evaluation.creativity}｜"
            f"反論力: {evaluation.rebuttal}"
        )

    @staticmethod
    def build_profile_report(user: User) -> str:
        scores = ChatLogRepository.fetch_riddle_scores(user)
        if not scores:
            return "あなたの回答傾向\n\n論理力        0.0\n発想力        0.0\n正答率        0%\n\nコメント\n評価データがありません。"

        total = len(scores)
        correctness_sum = sum(s.get("correctness", 0) for s in scores)
        reasoning_sum = sum(s.get("reasoning", 0) for s in scores)
        creativity_sum = sum(s.get("creativity", 0) for s in scores)
        rebuttal_sum = sum(s.get("rebuttal", 0) for s in scores)

        reasoning_avg = reasoning_sum / total
        creativity_avg = creativity_sum / total

        total_questions = total
        correct_count = sum(1 for s in scores if s.get("correctness", 0) >= 3)
        accuracy_rate = (
            round((correct_count / total_questions) * 100) if total_questions else 0
        )

        correctness_max = total_questions * 5
        reasoning_max = total_questions * 5
        creativity_max = total_questions * 5
        rebuttal_max = total_questions * 5

        correctness_rate = (
            round((correctness_sum / correctness_max) * 100)
            if correctness_max
            else 0
        )
        reasoning_rate = (
            round((reasoning_sum / reasoning_max) * 100) if reasoning_max else 0
        )
        creativity_rate = (
            round((creativity_sum / creativity_max) * 100) if creativity_max else 0
        )
        rebuttal_rate = (
            round((rebuttal_sum / rebuttal_max) * 100) if rebuttal_max else 0
        )

        if creativity_avg >= reasoning_avg + 0.5:
            comment_lines = [
                "あなたは発想力が高く、直感型の思考傾向があります。",
                "ただし論理説明を補強するとさらに説得力が増します。",
            ]
        elif reasoning_avg >= creativity_avg + 0.5:
            comment_lines = [
                "論理的に考える力が高く、筋道を立てるのが得意です。",
                "発想の幅を少し広げると表現力がさらに増します。",
            ]
        else:
            comment_lines = [
                "発想力と論理力のバランスが良いです。",
                "正答率を意識するとさらに安定します。",
            ]

        if accuracy_rate >= 60:
            comment_lines.append("正答率は合格レンジです。")
        else:
            comment_lines.append("正答率を上げるには、問題文の前提整理が有効です。")

        lines = [
            "あなたの回答傾向",
            "",
            f"正確性 {correctness_sum}/{correctness_max} ({correctness_rate}%)｜正答率 {accuracy_rate}%（正答率=正確性>=3 の割合）",
            f"論理性 {reasoning_sum}/{reasoning_max} ({reasoning_rate}%)｜論理力 {reasoning_avg:.1f}（問題数平均）",
            f"独創性 {creativity_sum}/{creativity_max} ({creativity_rate}%)｜発想力 {creativity_avg:.1f}（問題数平均）",
            f"反論力 {rebuttal_sum}/{rebuttal_max} ({rebuttal_rate}%)",
            "",
            "コメント",
            *comment_lines,
        ]
        return "\n".join(line + "  " if line else "" for line in lines)
