from django.db.models import Q

from securities.models import Company, Counting, ReportDocument


class EdinetRepository:
    @staticmethod
    def delete_existing_records(report_doc_list: list[ReportDocument]) -> None:
        delete_conditions = Q()

        for report_doc in report_doc_list:
            company = Company.objects.get(edinet_code=report_doc.edinet_code)
            delete_conditions |= Q(
                company=company, submit_date=report_doc.submit_date_time
            )

        Counting.objects.filter(delete_conditions).delete()
