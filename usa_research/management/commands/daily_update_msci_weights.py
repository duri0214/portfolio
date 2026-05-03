import io
import os
from datetime import datetime

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
        """
        処理フロー:
        1. 解析: 指定されたURLからHTTP HEADリクエストを送り、Last-Modifiedヘッダで鮮度を確認。更新があればPDFをダウンロードし、テキストを抽出。LLMで要約を生成する。
        2. 観察: DBから既存の最新レコードを取得する。
        3. 判断: HTTPヘッダの日付が既存レコードの日付より新しければ本処理へ。同じか古ければ終了（残心）。
        4. 本処理: 新規レコードをDBに保存する。
        """
        url = options["url"]
        self.stdout.write(f"Processing MSCI report from: {url}")

        result = self.update_report(url)

        if result.success:
            self.stdout.write(self.style.SUCCESS(result.message))
        else:
            self.stdout.write(self.style.WARNING(result.message))

    def update_report(self, pdf_url: str) -> MsciUpdateResult:
        """
        MSCIのPDFレポートをダウンロード・解析し、必要に応じてDBを更新します。

        シナリオ:
        1. HTTP HEADリクエストを送り、Last-Modifiedヘッダで鮮度を確認。
           - ヘッダの日付がDB内の最新レコードの日付以前であれば、早期リターンする。
        2. 更新があれば（またはHEAD失敗時）、PDFをダウンロードし、pypdfでテキストを抽出。
        3. 抽出されたテキストをOpenAI GPT-4oに渡し、LLMが「Country Weightsの要約」を生成。
        4. HTTPヘッダの Last-Modified をレポート日付として採用し、DBの最新レコードの日付と比較して新しい場合のみ保存。
        """
        # 0. 観察（最新レコードの取得）
        latest_record = MsciCountryWeightReport.objects.order_by("-report_date").first()

        # 1. 判断 (HTTP HEAD による鮮度チェック)
        report_date = None
        try:
            head_resp = requests.head(pdf_url, timeout=10)
            if head_resp.status_code == 200:
                last_modified_str = head_resp.headers.get("Last-Modified")
                if last_modified_str:
                    last_modified = datetime.strptime(
                        last_modified_str, "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    report_date = last_modified.date()
                    if latest_record and report_date <= latest_record.report_date:
                        return MsciUpdateResult(
                            True,
                            f"HTTP Head indicates no update since {latest_record.report_date}. Standing by.",
                        )
        except Exception as e:
            self.stdout.write(
                f"HEAD request failed, falling back to full download: {e}"
            )

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

        # 2. PDFダウンロード
        try:
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            pdf_content = response.content

            # HEADで取れなかった場合、GETのヘッダから取得試行
            if not report_date:
                last_modified_str = response.headers.get("Last-Modified")
                if last_modified_str:
                    last_modified = datetime.strptime(
                        last_modified_str, "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    report_date = last_modified.date()
        except Exception as e:
            return MsciUpdateResult(False, f"PDFダウンロード失敗: {str(e)}")

        if not report_date:
            return MsciUpdateResult(
                False, "レポートの日付（Last-Modified）を特定できませんでした。"
            )

        # 2. PDFからテキスト抽出
        try:
            reader = PdfReader(io.BytesIO(pdf_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            return MsciUpdateResult(False, f"PDFテキスト抽出失敗: {str(e)}")

        # 3. LLMによる要約
        prompt = f"""
            以下のMSCI Indexのレポート内容から、「Country Weight（国別株式比率）」を中心に内容を【日本語で】要約してください。
            
            【要約の観点】
            - 国別比率の概況
            - 前月比での大きな変化
            - 特筆すべき集中・分散の状況
            
            (Markdown形式で、日本語で要約を記述。各セクションの見出しには ##### を使用してください)
            
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
            summary_md = completion.answer
        except Exception as e:
            return MsciUpdateResult(False, f"LLM要約失敗: {str(e)}")

        # 5. 保存（冪等性は上流の判定で担保）
        MsciCountryWeightReport.objects.create(
            report_date=report_date, summary_md=summary_md, pdf_url=pdf_url
        )

        return MsciUpdateResult(
            True, f"Successfully processed report for {report_date}."
        )
