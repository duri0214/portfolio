import os

from openai import OpenAI

from lib.llm.valueobject.config import ModelDefaults


class LandReviewCommentGenerationError(Exception):
    """評価コメントのGPT生成を完了できない場合の例外。"""


class LandReviewCommentGenerator:
    """土壌診断通知表用のコメント下書きをOpenAIから取得する外部入力元。"""

    def generate(self, prompt: str) -> str:
        """指定した台帳の要約条件を基に、編集前提の評価コメントを生成する。"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LandReviewCommentGenerationError(
                "OPENAI_API_KEY が設定されていないため、GPT下書きを生成できません。"
            )

        try:
            response = OpenAI(api_key=api_key).chat.completions.create(
                model=ModelDefaults.TEXT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは土壌診断の通知表に載せる短い所見の下書きを作成します。",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as error:
            raise LandReviewCommentGenerationError(
                "GPT下書きの生成に失敗しました。時間をおいて再試行してください。"
            ) from error

        comment = response.choices[0].message.content or ""
        if not comment.strip():
            raise LandReviewCommentGenerationError(
                "GPT下書きが空のため、もう一度生成してください。"
            )
        return comment
