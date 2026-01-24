import logging
import zipfile
import markdown
import time

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from django.db import transaction
from .forms import UploadFileForm
from .models import Bank
from .domain.service.mufg_csv_service import MufgCsvService
from .domain.repository.mufg_repository import MufgRepository

logger = logging.getLogger(__name__)


class IndexView(TemplateView):
    template_name = "bank/index.html"


class MufgDepositUploadView(View):
    template_name = "bank/mufg_deposit_upload.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.csv_service = MufgCsvService()

    def get(self, request):
        form = UploadFileForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            start_time = time.time()
            uploaded_file = request.FILES["file"]
            bank = form.cleaned_data["bank"]
            try:
                processed_files, skipped_files, total_monthly_counts = (
                    self.handle_uploaded_file(uploaded_file, bank)
                )

                elapsed_time = time.time() - start_time
                total_count = sum(total_monthly_counts.values())
                msg_md = f"取り込みが完了しました（合計: {total_count}件, 処理時間: {elapsed_time:.2f}秒）。"
                if total_monthly_counts:
                    msg_md += "\n\n内訳:\n\n"
                    for m, c in sorted(total_monthly_counts.items()):
                        msg_md += f"- {m}: {c}件\n"

                msg_html = markdown.markdown(msg_md)
                messages.success(request, msg_html)

                if processed_files:
                    logger.info("-" * 40)
                    logger.info(f"Processed files: {', '.join(processed_files)}")
                if skipped_files:
                    logger.info(f"Skipped non-CSV files: {', '.join(skipped_files)}")
                if processed_files or skipped_files:
                    logger.info("-" * 40)

            except Exception as e:
                logger.error(f"Upload error: {str(e)}", exc_info=True)
                # 全体がロールバックされたことを明示する。Markdownの構造を保つため2つの改行を入れる
                error_msg_md = f"**エラーが発生しました（処理は中断され、データは保存されていません）**\n\n{str(e)}"
                error_msg_html = markdown.markdown(error_msg_md)
                messages.error(request, error_msg_html)
            return redirect("bank:mufg_deposit_upload")
        return render(request, self.template_name, {"form": form})

    def handle_uploaded_file(self, uploaded_file, bank):
        filename = uploaded_file.name.lower()

        processed_files = []
        skipped_files = []
        total_monthly_counts = {}
        repository = MufgRepository(bank)

        with transaction.atomic():
            if filename.endswith(".zip"):
                logger.info("=" * 40)
                logger.info(f"Start processing ZIP file: {uploaded_file.name}")
                with zipfile.ZipFile(uploaded_file) as z:
                    for name in z.namelist():
                        if name.lower().endswith(".csv"):
                            logger.info(f"Processing file from ZIP: {name}")
                            try:
                                with z.open(name) as f:
                                    # MUFG CSVは CP932 (Shift-JIS)
                                    content = f.read().decode("cp932")
                                    rows = self.csv_service.process_csv_content(
                                        content, filename=name
                                    )
                                    # 常に画面で選択された口座を使用する
                                    monthly_counts = repository.save_rows(rows)
                                    for m, c in monthly_counts.items():
                                        total_monthly_counts[m] = (
                                            total_monthly_counts.get(m, 0) + c
                                        )

                                    file_count = sum(monthly_counts.values())
                                    logger.info(
                                        f"  -> {name}: New records: {file_count}"
                                    )
                                    processed_files.append(name)
                            except ValueError as e:
                                if "重複" in str(e):
                                    # ZIP内の1件でも重複があれば全体を例外で中断（ロールバック）
                                    logger.error(
                                        f"  -> {name}: Duplicate found. Aborting entire batch."
                                    )
                                    raise ValueError(
                                        f"ファイル '{name}' で重複データが見つかったため、全体の取り込みを中止しました（1件も保存されていません）。"
                                    )
                                else:
                                    raise e
                        else:
                            logger.info(f"Skipping non-CSV file in ZIP: {name}")
                            skipped_files.append(name)
            elif filename.endswith(".csv"):
                # 直接CSVがアップロードされた場合
                logger.info("=" * 40)
                logger.info(f"Processing direct CSV: {uploaded_file.name}")
                try:
                    content = uploaded_file.read().decode("cp932")
                    rows = self.csv_service.process_csv_content(
                        content, filename=uploaded_file.name
                    )
                    # 常に画面で選択された口座を使用する
                    monthly_counts = repository.save_rows(rows)
                    for m, c in monthly_counts.items():
                        total_monthly_counts[m] = total_monthly_counts.get(m, 0) + c

                    file_count = sum(monthly_counts.values())
                    logger.info(f"  -> {uploaded_file.name}: New records: {file_count}")
                    processed_files.append(uploaded_file.name)
                except ValueError as e:
                    if "重複" in str(e):
                        logger.error(
                            f"  -> {uploaded_file.name}: Duplicate found. Aborting."
                        )
                        raise ValueError(
                            f"ファイル '{uploaded_file.name}' で重複データが見つかったため、取り込みを中止しました（1件も保存されていません）。"
                        )
                    else:
                        raise e
            else:
                raise ValueError("CSVまたはZIPファイルのみアップロード可能です。")

        return processed_files, skipped_files, total_monthly_counts


class MufgDepositDeleteView(View):
    @staticmethod
    def post(request):
        bank_id = request.POST.get("bank")
        if not bank_id:
            messages.error(request, "口座を選択してください。")
            return redirect("bank:mufg_deposit_upload")

        start_time = time.time()
        bank = get_object_or_404(Bank, pk=bank_id)
        repository = MufgRepository(bank)
        monthly_counts = repository.delete_all_data()

        elapsed_time = time.time() - start_time
        total_count = sum(monthly_counts.values())
        msg_md = f"{bank.name} のデータ {total_count} 件を削除しました（処理時間: {elapsed_time:.2f}秒）。"
        if monthly_counts:
            msg_md += "\n\n内訳:\n\n"
            for m, c in sorted(monthly_counts.items()):
                msg_md += f"- {m}: {c}件\n"

        msg_html = markdown.markdown(msg_md)
        messages.success(request, msg_html)
        return redirect("bank:mufg_deposit_upload")
