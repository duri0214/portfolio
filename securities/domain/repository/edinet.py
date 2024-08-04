from securities.domain.valueobject.edinet import CountingData
from securities.models import Company, Counting, ReportDocument


class EdinetRepository:
    @staticmethod
    def find_by_doc_id(doc_id: str) -> ReportDocument:
        return ReportDocument.objects.get(doc_id=doc_id)

    @staticmethod
    def delete_existing_records(report_doc: ReportDocument):
        company = Company.objects.get(edinet_code=report_doc.edinet_code)
        Counting.objects.filter(
            company=company, submit_date=report_doc.submit_date_time
        ).delete()

    @staticmethod
    def insert(report_doc: ReportDocument, counting_data: CountingData):
        company = Company.objects.get(edinet_code=counting_data.edinet_code)
        Counting.objects.create(
            period_start=report_doc.period_start,
            period_end=report_doc.period_end,
            submit_date=report_doc.submit_date_time,
            avg_salary=counting_data.avg_salary,
            avg_tenure=counting_data.avg_tenure_years_combined,
            avg_age=counting_data.avg_age_years_combined,
            number_of_employees=counting_data.number_of_employees,
            company=company,
        )

        edinet_codes = [report_doc.edinet_code for report_doc in doc_attr_dict.values()]
        edinet_code_to_company = {
            company.edinet_code: company
            for company in Company.objects.filter(edinet_code__in=edinet_codes)
        }
        insert_objects = [
            x.to_entity(
                doc_attr_dict,
                edinet_code_to_company,
            )
            for x in counting_data_dict.values()
        ]
        Counting.objects.bulk_create(insert_objects)
