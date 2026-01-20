import logging
import zipfile

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from django.db import transaction
from .forms import UploadFileForm
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
            uploaded_file = request.FILES["file"]
            bank = form.cleaned_data["bank"]
            try:
                processed_files, skipped_files, duplicated_files, total_created = (
                    self.handle_uploaded_file(uploaded_file, bank)
                )
                msg = (
                    f"取り込みが完了しました（処理: {len(processed_files)}ファイル）。"
                )
                messages.success(request, msg)

                if processed_files:
                    logger.info("-" * 40)
                    logger.info(f"Processed files: {', '.join(processed_files)}")
                if skipped_files:
                    logger.info(f"Skipped non-CSV files: {', '.join(skipped_files)}")
                if processed_files or skipped_files:
                    logger.info("-" * 40)

            except Exception as e:
                logger.error(f"Upload error: {str(e)}", exc_info=True)
                messages.error(request, f"エラーが発生しました: {str(e)}")
            return redirect("bank:mufg_deposit_upload")
        return render(request, self.template_name, {"form": form})

    def handle_uploaded_file(self, uploaded_file, bank):
        filename = uploaded_file.name.lower()

        processed_files = []
        skipped_files = []
        duplicated_files = []
        total_created = 0
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
                                    created = repository.save_rows(rows)
                                    total_created += created
                                    logger.info(f"  -> {name}: New records: {created}")
                                    processed_files.append(name)
                            except ValueError as e:
                                if "重複" in str(e):
                                    # ZIP内の1件でも重複があれば全体を例外で中断（ロールバック）
                                    logger.error(
                                        f"  -> {name}: Duplicate found. Aborting entire batch."
                                    )
                                    raise ValueError(
                                        f"ファイル '{name}' で重複データが見つかったため、全体の取り込みを中止しました。"
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
                    created = repository.save_rows(rows)
                    total_created += created
                    logger.info(f"  -> {uploaded_file.name}: New records: {created}")
                    processed_files.append(uploaded_file.name)
                except ValueError as e:
                    if "重複" in str(e):
                        logger.error(
                            f"  -> {uploaded_file.name}: Duplicate found. Aborting."
                        )
                        raise ValueError(
                            f"ファイル '{uploaded_file.name}' で重複データが見つかったため、取り込みを中止しました。"
                        )
                    else:
                        raise e
            else:
                raise ValueError("CSVまたはZIPファイルのみアップロード可能です。")

        return processed_files, skipped_files, duplicated_files, total_created
