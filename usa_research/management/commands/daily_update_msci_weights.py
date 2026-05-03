import io
import os
import re
from datetime import datetime
from typing import Optional, Tuple

import requests
from django.core.management.base import BaseCommand
from pypdf import PdfReader

from lib.llm.service.completion import LlmCompletionService
from lib.llm.valueobject.completion import Message, RoleType
from lib.llm.valueobject.config import OpenAIGptConfig
from usa_research.domain.valueobject.msci import MsciUpdateResult
from usa_research.models import MsciCountryWeightReport


class Command(BaseCommand):
    help = (
        "MSCIのPDFレポートからCountry Weightを抽出し、DBを更新します（日次実行対応）。"
    )

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
        """
        # API設定
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return MsciUpdateResult(False, "OPENAI_API_KEY is not set.")

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

        # 2. PDFからテキスト抽出
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            return MsciUpdateResult(False, f"PDFテキスト抽出失敗: {str(e)}")

        # 3. LLMによる日付抽出と要約
        prompt = f"""
            以下のMSCI Indexのレポート内容から、レポートの日付（Report Date）を抽出し、
            その後「Country Weight（国別株式比率）」を中心に内容を【日本語で】要約してください。
            
            【要約の観点】
            - 国別比率の概況
            - 前月比での大きな変化
            - 特筆すべき集中・分散の状況
            
            【出力フォーマット】
            Report Date: YYYY-MM-DD
            
            (ここにMarkdown形式で、日本語で要約を記述。各セクションの見出しには ##### を使用してください)
            
            ※注意: 要約の部分に 'Report Date' という文字列を含めないでください。
            
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
            llm_response = completion.answer
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

        # 5. 観察（最新レコードの取得）と判断
        latest_record = MsciCountryWeightReport.objects.order_by("-report_date").first()

        if latest_record is not None:
            # 既にレコードがある場合：日付を比較
            if report_date <= latest_record.report_date:
                return MsciUpdateResult(
                    True, f"Already updated for {report_date}. Standing by."
                )
        else:
            # レコードがゼロの場合
            self.stdout.write("Initial data migration or empty DB detected.")

        # 6. 本処理：新規作成
        MsciCountryWeightReport.objects.create(
            report_date=report_date, summary_md=summary_md, pdf_url=pdf_url
        )

        return MsciUpdateResult(
            True, f"Successfully processed report for {report_date}."
        )

    @staticmethod
    def _parse_llm_response(response: str) -> Tuple[Optional[str], str]:
        """
        LLMの応答から日付と要約を抽出する。
        """
        # 日付の抽出
        date_match = re.search(r"Report Date:\s*(\d{4}-\d{2}-\d{2})", response)
        report_date = date_match.group(1) if date_match else None

        # 要約の抽出 (Report Date の行を除去)
        lines = response.strip().splitlines()
        summary_lines = []
        for line in lines:
            if re.search(r"Report Date:\s*\d{4}-\d{2}-\d{2}", line):
                continue
            summary_lines.append(line)

        summary_md = "\n".join(summary_lines).strip()

        return report_date, summary_md
