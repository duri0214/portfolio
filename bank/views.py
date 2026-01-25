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


class MufgLivingCostAnalysisView(TemplateView):
    template_name = "bank/mufg_analysis_living_cost.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bank_id = self.request.GET.get("bank")
        only_40k = self.request.GET.get("only_40k") == "true"

        if not bank_id:
            context["error"] = "銀行を選択してください。"
            context["banks"] = Bank.objects.all()
            return context

        bank = get_object_or_404(Bank, pk=bank_id)
        repository = MufgRepository(bank)
        transactions = list(repository.get_living_cost_transactions(only_40k=only_40k))

        # 分析ロジック
        monthly_counts = {}
        dates = []
        intervals = []
        prev_date = None

        for tx in transactions:
            month = tx.trade_date.strftime("%Y-%m")
            monthly_counts[month] = monthly_counts.get(month, 0) + 1
            dates.append(tx.trade_date)

            if prev_date:
                diff = (tx.trade_date - prev_date).days
                intervals.append(diff)
            prev_date = tx.trade_date

        stats = {}
        if intervals:
            stats["min_interval"] = min(intervals)
            stats["max_interval"] = max(intervals)
            stats["avg_interval"] = sum(intervals) / len(intervals)
        else:
            stats["min_interval"] = stats["max_interval"] = stats["avg_interval"] = 0

        # 月別取引件数（時系列グラフ用）
        chart_labels = []
        chart_data = []
        frequency_dist = {}
        if monthly_counts:
            # 度数分布（月ごとの取引件数の分布）
            for count in monthly_counts.values():
                frequency_dist[count] = frequency_dist.get(count, 0) + 1

            # 最小の月から最大の月まで埋める
            sorted_months = sorted(monthly_counts.keys())
            start_month_str = sorted_months[0]
            end_month_str = sorted_months[-1]

            from datetime import datetime
            from dateutil.relativedelta import relativedelta

            curr = datetime.strptime(start_month_str, "%Y-%m")
            end = datetime.strptime(end_month_str, "%Y-%m")

            while curr <= end:
                m_str = curr.strftime("%Y-%m")
                chart_labels.append(m_str)
                chart_data.append(monthly_counts.get(m_str, 0))
                curr += relativedelta(months=1)

        context.update(
            {
                "bank": bank,
                "only_40k": only_40k,
                "transactions": transactions,
                "monthly_counts": sorted(monthly_counts.items()),
                "frequency_dist": sorted(frequency_dist.items()),
                "chart_labels": chart_labels,
                "chart_data": chart_data,
                "stats": stats,
                "banks": Bank.objects.all(),
            }
        )
        return context


class MufgCategoryMonthlyAnalysisView(TemplateView):
    template_name = "bank/mufg_analysis_category_monthly.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bank_id = self.request.GET.get("bank")

        if not bank_id:
            context["error"] = "銀行を選択してください。"
            context["banks"] = Bank.objects.all()
            return context

        bank = get_object_or_404(Bank, pk=bank_id)
        repository = MufgRepository(bank)
        data = repository.get_category_monthly_stats()

        # クロス集計テーブルの構築
        # 行: 月, 列: カテゴリ
        pivot_table = []
        # 合計値が0より大きいカテゴリのみ抽出
        active_categories = []
        for cat in data["categories"]:
            cat_total = sum(
                data["stats"].get((month, cat), {"payment": 0})["payment"]
                for month in data["months"]
            )
            if cat_total > 0:
                active_categories.append(cat)

        for month in data["months"]:
            row = {"month": month, "category_values": []}
            total_payment = 0
            for cat in active_categories:
                val = data["stats"].get((month, cat), {"payment": 0, "deposit": 0})
                payment = val["payment"]
                row["category_values"].append(payment)
                total_payment += payment
            row["total"] = total_payment
            pivot_table.append(row)

        # 列ごとの合計（カテゴリごとの合計）を計算
        category_totals = []
        for cat in active_categories:
            total = sum(
                data["stats"].get((month, cat), {"payment": 0})["payment"]
                for month in data["months"]
            )
            category_totals.append(total)

        context.update(
            {
                "bank": bank,
                "categories": active_categories,
                "pivot_table": pivot_table,
                "category_totals": category_totals,
                "grand_total": sum(category_totals),
                "banks": Bank.objects.all(),
            }
        )
        return context


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
                                    # TODO: 銀行（Bank）によってエンコーディングが異なる可能性があるため、将来的に可変にすることを検討
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
                                # MufgRepository.save_rows は重複検知時に ValueError("...重複...") を投げる
                                if "重複" in str(e):
                                    # ZIP内の1件でも重複があれば全体を例外で中断（ロールバック）
                                    logger.error(
                                        f"  -> {name}: Duplicate found. Aborting entire batch."
                                    )
                                    raise ValueError(
                                        f"ファイル '{name}' で重複データが見つかったため、全体の取り込みを中止しました（1件も保存されていません）。"
                                    )
                                raise e
                        else:
                            logger.info(f"Skipping non-CSV file in ZIP: {name}")
                            skipped_files.append(name)
            elif filename.endswith(".csv"):
                # 直接CSVがアップロードされた場合
                logger.info("=" * 40)
                logger.info(f"Processing direct CSV: {uploaded_file.name}")
                try:
                    # TODO: 銀行（Bank）によってエンコーディングが異なる可能性があるため、将来的に可変にすることを検討
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
                    # MufgRepository.save_rows は重複検知時に ValueError("...重複...") を投げる
                    if "重複" in str(e):
                        logger.error(
                            f"  -> {uploaded_file.name}: Duplicate found. Aborting."
                        )
                        raise ValueError(
                            f"ファイル '{uploaded_file.name}' で重複データが見つかったため、取り込みを中止しました（1件も保存されていません）。"
                        )
                    raise e
            else:
                raise ValueError("CSVまたはZIPファイルのみアップロード可能です。")

        return processed_files, skipped_files, total_monthly_counts


class MufgDepositDeleteView(View):
    @staticmethod
    def post(request):
        bank_id = request.POST.get("bank")
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
