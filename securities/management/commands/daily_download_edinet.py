import logging
import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand

from config import settings
from securities.domain.service.xbrl import XbrlService
from securities.models import ReportDocument, Company, Counting


class Command(BaseCommand):
    help = "Download edinet data"

    def handle(self, *args, **options):
        report_doc_list = ReportDocument.objects.filter(download_reserved=True)[:20]

        work_dir = Path(settings.MEDIA_ROOT) / "sec"
        if not work_dir.exists():
            work_dir.mkdir(parents=True, exist_ok=True)

        companies = Company.objects.all()
        company_mst = {c.edinet_code: c for c in companies}

        service = XbrlService()
        service.repository.delete_existing_records(report_doc_list)

        counting_list: list[Counting] = []
        for report_doc in report_doc_list:
            service.download_xbrl(report_doc=report_doc, work_dir=work_dir)
            counting_data = service.make_counting_data(work_dir=work_dir)
            counting = Counting(
                period_start=report_doc.period_start,
                period_end=report_doc.period_end,
                submit_date=report_doc.submit_date_time,
                avg_salary=counting_data.avg_salary,
                avg_tenure=counting_data.avg_tenure_years,
                avg_age=counting_data.avg_age_years_combined,
                number_of_employees=counting_data.number_of_employees,
                company=company_mst[report_doc.company.edinet_code],
            )
            counting_list.append(counting)
            os.remove(work_dir / f"{report_doc.doc_id}.zip")

        Counting.objects.bulk_create(counting_list)
        logging.info(f"計数データ作成完了: {len(report_doc_list)}")
        shutil.rmtree(work_dir)

        ReportDocument.objects.filter(
            id__in=[report_document.id for report_document in report_doc_list]
        ).update(download_reserved=False)

        self.stdout.write(self.style.SUCCESS("Successfully download edinet data"))
