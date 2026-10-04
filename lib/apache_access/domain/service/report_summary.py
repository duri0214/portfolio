"""Generate constrained GPT summaries from anonymous Apache report aggregates."""

import json
import os

from openai import OpenAI

from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReport,
    ApacheAccessReportSummaryError,
)
from lib.llm.valueobject.config import ModelDefaults


MAX_OUTPUT_TOKENS = 250
MAX_SUMMARY_CHARACTERS = 500
PROHIBITED_SUMMARY_PHRASES = (
    "攻撃",
    "情報漏えい",
    "情報漏洩",
    "自動遮断",
    "遮断",
    "自動ブロック",
    "ブロック",
)
SUMMARY_INSTRUCTIONS = """\
匿名化済みのApacheアクセス集計値だけを、管理者向けに日本語で短く要約してください。
入力以外の情報を補わず、IPアドレス、URL、クエリ文字列、User-Agent、ログ行、エラー詳細には触れないでください。
出力は必ず次の2行だけにしてください。
観測: 入力中の数値を少なくとも1つ示す、客観的な事実。
推測: 数値から考えられることを「可能性があります」など条件付きで述べる。
攻撃や情報漏えいを断定せず、アクセス遮断などの自動対処を提案しないでください。
"""


class ApacheAccessReportSummaryService:
    """Generate a bounded GPT summary from an allowlisted report payload."""

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    @classmethod
    def from_environment(cls) -> "ApacheAccessReportSummaryService | None":
        """Create a summary service only when the feature flag is enabled."""
        enabled = os.getenv("APACHE_ACCESS_GPT_ENABLED", "False").lower() == "true"
        if not enabled:
            return None

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ApacheAccessReportSummaryError(
                "GPT要約を有効にするにはOPENAI_API_KEYが必要です。"
            )
        return cls(api_key)

    def summarize(self, report: ApacheAccessReport) -> str:
        """Return a two-line summary without logging API input or output."""
        summary_input = json.dumps(
            report.summary_input(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            response = self.client.responses.create(
                model=ModelDefaults.TEXT_MODEL,
                instructions=SUMMARY_INSTRUCTIONS,
                input=summary_input,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            )
        except Exception as error:
            raise ApacheAccessReportSummaryError(
                "GPT要約を生成できませんでした。"
            ) from error

        summary = response.output_text
        if not isinstance(summary, str):
            raise ApacheAccessReportSummaryError(
                "GPT要約の形式を確認できませんでした。"
            )
        summary = summary.strip()
        self._validate_summary(summary)
        return summary

    @staticmethod
    def _validate_summary(summary: str) -> None:
        """Reject summaries that lack evidence labels or make prohibited claims."""
        lines = summary.splitlines()
        if (
            len(lines) != 2
            or not lines[0].startswith("観測:")
            or not lines[1].startswith("推測:")
            or not any(character.isdigit() for character in summary)
        ):
            raise ApacheAccessReportSummaryError(
                "GPT要約の観測値または推測の区別を確認できませんでした。"
            )
        if len(summary) > MAX_SUMMARY_CHARACTERS:
            raise ApacheAccessReportSummaryError("GPT要約が長すぎます。")
        if any(phrase in summary for phrase in PROHIBITED_SUMMARY_PHRASES):
            raise ApacheAccessReportSummaryError(
                "GPT要約に許可されない表現があります。"
            )
