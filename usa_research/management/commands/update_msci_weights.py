import os
import requests
import re
import io
from datetime import datetime
from typing import Optional, Tuple
from pypdf import PdfReader
from django.core.management.base import BaseCommand

from usa_research.models import MsciCountryWeightReport
from usa_research.domain.valueobject.msci import MsciUpdateResult
from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig


class Command(BaseCommand):
    help = "MSCIのPDFレポートからCountry Weightを抽出し、LLMで要約してDBに保存します。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            default="https://www.msci.com/documents/10199/178e6643-6ae6-47b9-82be-e1fc565ededb",
            help="MSCI PDFのURL",
        )

    def handle(self, *args, **options):
        url = options["url"]
        self.stdout.write(f"Processing MSCI report from: {url}")

        result = self.update_report(url)

        if result.success:
            self.stdout.write(self.style.SUCCESS(result.message))
        else:
            self.stdout.write(self.style.WARNING(result.message))

    def update_report(self, pdf_url: str) -> MsciUpdateResult:
        """
        MSCIのPDFレポートを処理し、DBを更新します。

        処理フロー:
        1. PDFのダウンロード: 指定されたURLからPDFバイナリを取得。
        2. テキスト抽出: pypdfを使用してPDFから全テキストを抽出（LLMの入力用）。
        3. LLMによる解析:
           - 抽出テキストから「レポートの日付」を特定。
           - 「Country Weights」を中心に内容を要約。
        4. レスポンスのパース: LLMの出力から日付とMarkdown形式の要約を分離。
        5. 重複チェック: 特定された日付が既にDB（report_date）に存在するか確認。
           - 既に存在する場合は、API消費を抑えるため要約の保存を行わずスキップ。
        6. DB保存: 新規日付の場合のみ、要約とURLを保存。
        """
        # API設定
        api_key = os.getenv("OPENAI_API_KEY")
        config = OpenAIGptConfig(
            api_key=api_key,
            model="gpt-4o",
            max_tokens=2000,
        )
        llm_service = LlmCompletionService(config)

        # 1. PDFダウンロード
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            pdf_content = response.content
        except Exception as e:
            return MsciUpdateResult(False, f"PDFダウンロード失敗: {str(e)}")

        # 2. PDFからテキスト抽出 (LLMに渡すため)
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            return MsciUpdateResult(False, f"PDFテキスト抽出失敗: {str(e)}")

        # 3. LLMによる日付抽出と要約
        prompt = f"""
            以下のMSCI Index의 レポート内容から、レポートの日付（Report Date）を抽出し、
            その後「Country Weight（国別株式比率）」を中心に内容を要約してください。
            
            【要約の観点】
            - 国別比率の概況
            - 前月比での大きな変化
            - 特筆すべき集中・分散の兆候
            
            【出力フォーマット】
            Report Date: YYYY-MM-DD
            ---
            # Summary
            (ここにMarkdown形式で要約を記述)
            
            ---
            【レポート内容】
            {text}
            """
        messages = [
            Message(
                role=RoleType.SYSTEM,
                content="あなたは金融アナリストです。提供されたレポートを正確に要約してください。",
            ),
            Message(role=RoleType.USER, content=prompt),
        ]

        try:
            completion = llm_service.retrieve_answer(messages, max_messages=2)
            llm_response = completion.choices[0].message.content
        except Exception as e:
            return MsciUpdateResult(False, f"LLM要約失敗: {str(e)}")

        # 4. LLM応答のパース
        report_date_str, summary_md = self._parse_llm_response(llm_response)
        if not report_date_str:
            return MsciUpdateResult(
                False, "LLM応答からレポート日付を抽出できませんでした。"
            )

        try:
            report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        except ValueError:
            return MsciUpdateResult(False, f"不適切な日付形式です: {report_date_str}")

        # 5. DB保存済みの最新日付と比較
        if MsciCountryWeightReport.objects.filter(report_date=report_date).exists():
            return MsciUpdateResult(
                False, f"日付 {report_date} のレポートは既に保存済みです。"
            )

        # 6. 保存
        MsciCountryWeightReport.objects.create(
            report_date=report_date, summary_md=summary_md, pdf_url=pdf_url
        )

        return MsciUpdateResult(True, f"日付 {report_date} のレポートを保存しました。")

    @staticmethod
    def _parse_llm_response(response: str) -> Tuple[Optional[str], str]:
        """
        LLMの応答から日付と要約を抽出する。
        """
        date_match = re.search(r"Report Date:\s*(\d{4}-\d{2}-\d{2})", response)
        report_date = date_match.group(1) if date_match else None

        # summary_mdは "---" 以降の部分とする
        parts = response.split("---", 1)
        summary_md = parts[1].strip() if len(parts) > 1 else response

        return report_date, summary_md
