import json

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningReviewAnalysisResult,
)


class GoogleMapsReviewAnalysisClient:
    """Google Mapsレビューを出店計画向けにLLM分析するクライアント。"""

    MODEL_NAME = "gpt-5-mini"
    PROMPT_VERSION = "store-planning-review-analysis-v1"

    def __init__(self, api_key: str, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.service = LlmCompletionService(
            OpenAIGptConfig(api_key=api_key, model=model_name, max_tokens=1200)
        )

    def analyze_reviews(self, reviews: list) -> list[StorePlanningReviewAnalysisResult]:
        """
        保存済みレビュー群をまとめて分析し、レビュー単位の構造化結果に変換する。
        """
        if not reviews:
            return []

        messages = [
            Message(
                role=RoleType.SYSTEM,
                content=(
                    "あなたは出店計画のためにGoogle Mapsレビューを分析する専門家です。"
                    "回答はJSON配列だけにしてください。"
                ),
            ),
            Message(role=RoleType.USER, content=self._prompt(reviews)),
        ]
        result = self.service.retrieve_answer(messages, max_messages=2)
        return self._parse_results(result.answer)

    def _prompt(self, reviews: list) -> str:
        review_lines = []
        for review in reviews:
            review_lines.append(
                {
                    "review_id": review.id,
                    "place_name": review.place_name,
                    "rating": review.rating,
                    "review_text": review.review_text,
                }
            )
        review_json = json.dumps(review_lines, ensure_ascii=False)
        return (
            "次のGoogle Mapsレビューを分析してください。\n"
            "各レビューについて、sentiment は positive/negative/neutral のいずれか、"
            "sentiment_score は -100 から 100 の整数にしてください。\n"
            "one_line_summary は店舗評判を1文で、issue は課題点、"
            "next_action は出店計画で取るべき次アクション、"
            "location_insight は立地に関する示唆を書いてください。\n"
            "JSON配列の各要素は review_id, sentiment, sentiment_score, "
            "one_line_summary, issue, next_action, location_insight を含めてください。\n"
            f"レビュー: {review_json}"
        )

    @staticmethod
    def _parse_results(answer: str) -> list[StorePlanningReviewAnalysisResult]:
        try:
            raw_items = json.loads(answer)
        except json.JSONDecodeError:
            return []
        if not isinstance(raw_items, list):
            return []

        results = []
        for item in raw_items:
            if not isinstance(item, dict) or "review_id" not in item:
                continue
            sentiment_score = item.get("sentiment_score") or 0
            results.append(
                StorePlanningReviewAnalysisResult(
                    review_id=int(item["review_id"]),
                    sentiment=item.get("sentiment") or "neutral",
                    sentiment_score=int(sentiment_score),
                    one_line_summary=item.get("one_line_summary") or "",
                    issue=item.get("issue") or "",
                    next_action=item.get("next_action") or "",
                    location_insight=item.get("location_insight") or "",
                    raw_response=item,
                )
            )
        return results
