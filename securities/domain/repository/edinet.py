import logging
from datetime import datetime

from securities.domain.valueobject.edinet import ResponseData, CountingData
from securities.models import Company, Counting


class EdinetRepository:
    @staticmethod
    def delete_existing_records(response_data_list: list[ResponseData]):
        edinet_codes = [data.results[0].edinet_code for data in response_data_list]
        edinet_code_to_company = {
            company.edinet_code: company
            for company in Company.objects.filter(edinet_code__in=edinet_codes)
        }
        for data in response_data_list:
            edinet_code = data.results[0].edinet_code
            submit_date = datetime.strptime(
                data.results[0].submit_date_time, "%Y-%m-%d %H:%M"
            )
            company = edinet_code_to_company[edinet_code]
            Counting.objects.filter(company=company, submit_date=submit_date).delete()

    @staticmethod
    def bulk_insert(
        doc_attr_dict: dict[str, ResponseData],
        counting_data_dict: dict[str, CountingData],
    ):
        # Delete the CountingData instances whose 'edinet_code' is not in 'doc_attr_dict'
        for edinet_code in list(counting_data_dict.keys()):
            if edinet_code not in doc_attr_dict:
                del counting_data_dict[edinet_code]
                logging.warning(
                    f"{edinet_code} の CountingData が doc_attr_dict に見つからなかったので CountingData から削除しました"
                )

        edinet_codes = [data.results[0].edinet_code for data in doc_attr_dict.values()]
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