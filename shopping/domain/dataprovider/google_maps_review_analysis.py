import json

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningPlaceSummaryResult,
    StorePlanningReviewAnalysisResult,
)


class GoogleMapsReviewAnalysisClient:
    """Google Mapsレビューを出店計画向けにLLM分析するクライアント。"""

    MODEL_NAME = "gpt-5-mini"
    PROMPT_VERSION = "store-planning-review-analysis-v3"

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

    def analyze_place_summaries(
        self, place_review_groups: list[dict]
    ) -> list[StorePlanningPlaceSummaryResult]:
        """
        店舗ごとのレビュー群を分析し、店舗単位のサマリー結果に変換する。
        """
        if not place_review_groups:
            return []

        messages = [
            Message(
                role=RoleType.SYSTEM,
                content=(
                    "あなたは出店計画のためにGoogle Mapsレビューを店舗単位で分析する専門家です。"
                    "回答はJSON配列だけにしてください。"
                ),
            ),
            Message(
                role=RoleType.USER,
                content=self._place_summary_prompt(place_review_groups),
            ),
        ]
        result = self.service.retrieve_answer(messages, max_messages=2)
        return self._parse_place_summary_results(result.answer)

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
            "one_line_summary は課題を含めず、店舗評判の特徴だけを1文で、issue は課題点、"
            "location_insight は立地に関する示唆を書いてください。\n"
            "JSON配列の各要素は review_id, sentiment, sentiment_score, "
            "one_line_summary, issue, location_insight を含めてください。\n"
            f"レビュー: {review_json}"
        )

    def _place_summary_prompt(self, place_review_groups: list[dict]) -> str:
        place_json = json.dumps(place_review_groups, ensure_ascii=False)
        return (
            "次のGoogle Mapsレビューを店舗単位で集約分析してください。\n"
            "各店舗について、レビュー群のポジティブ要因とネガティブ要因を比較し、"
            "店舗として何が評価され、何が課題になるかを抽出してください。\n"
            "sentiment_score は店舗全体の評判を -100 から 100 の整数にしてください。\n"
            "positive_count と negative_count はレビュー群の中で主要因として扱った件数にしてください。\n"
            "one_line_summary は課題を含めず、店舗評判の特徴だけを1文で、issue は課題点、"
            "location_insight は立地に関する示唆を書いてください。\n"
            "JSON配列の各要素は google_place_id, sentiment_score, positive_count, "
            "negative_count, one_line_summary, issue, location_insight を含めてください。\n"
            f"店舗別レビュー: {place_json}"
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
            review_id = GoogleMapsReviewAnalysisClient._to_int(item.get("review_id"))
            if review_id is None:
                continue
            results.append(
                StorePlanningReviewAnalysisResult(
                    review_id=review_id,
                    sentiment=item.get("sentiment") or "neutral",
                    sentiment_score=GoogleMapsReviewAnalysisClient._to_int(
                        item.get("sentiment_score"), default=0
                    ),
                    one_line_summary=item.get("one_line_summary") or "",
                    issue=item.get("issue") or "",
                    location_insight=item.get("location_insight") or "",
                    raw_response=item,
                )
            )
        return results

    @staticmethod
    def _parse_place_summary_results(
        answer: str,
    ) -> list[StorePlanningPlaceSummaryResult]:
        try:
            raw_items = json.loads(answer)
        except json.JSONDecodeError:
            return []
        if not isinstance(raw_items, list):
            return []

        results = []
        for item in raw_items:
            if not isinstance(item, dict) or "google_place_id" not in item:
                continue
            results.append(
                StorePlanningPlaceSummaryResult(
                    google_place_id=str(item["google_place_id"]),
                    sentiment_score=GoogleMapsReviewAnalysisClient._to_int(
                        item.get("sentiment_score"), default=0
                    ),
                    positive_count=GoogleMapsReviewAnalysisClient._to_int(
                        item.get("positive_count"), default=0
                    ),
                    negative_count=GoogleMapsReviewAnalysisClient._to_int(
                        item.get("negative_count"), default=0
                    ),
                    one_line_summary=item.get("one_line_summary") or "",
                    issue=item.get("issue") or "",
                    location_insight=item.get("location_insight") or "",
                    raw_response=item,
                )
            )
        return results

    @staticmethod
    def _to_int(value, default=None):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
