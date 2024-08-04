import datetime
import logging
import os
import shutil
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import requests
from arelle import Cntlr
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from lib.zipfileservice import ZipFileService
from securities.domain.repository.edinet import EdinetRepository
from securities.domain.valueobject.edinet import CountingData, RequestData
from securities.models import Company, ReportDocument

SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT = 1


class XbrlService:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        if not self.work_dir.exists():
            self.work_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.work_dir / "temp"
        self.repository = EdinetRepository()

    @staticmethod
    def fetch_securities_report(request_data: RequestData) -> list[ReportDocument]:
        """
        Args:
            request_data: APIへのリクエスト条件

        Returns:
            list[ReportDocument]: A list of ReportDocument objects.
        """
        report_doc_list: list[ReportDocument] = []
        for day in request_data.day_list:
            url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
            params = {
                "date": day,
                "type": request_data.SECURITIES_REPORT_AND_META_DATA,
                "Subscription-Key": os.environ.get("EDINET_API_KEY"),
            }
            res = requests.get(url, params=params)
            res.raise_for_status()

            for item in res.json().get("results", []):
                submit_date_string = item.get("submitDateTime")
                if submit_date_string is None:
                    continue
                ordinance_code = item.get("ordinanceCode")
                form_code = item.get("formCode")
                if not (ordinance_code == "010" and form_code == "030000"):
                    continue
                submit_date_time = timezone.make_aware(
                    datetime.strptime(submit_date_string, "%Y-%m-%d %H:%M")
                )
                ope_date_time_string = item.get("opeDateTime")
                ope_date_time = (
                    timezone.make_aware(
                        datetime.strptime(ope_date_time_string, "%Y-%m-%d %H:%M")
                    )
                    if ope_date_time_string
                    else None
                )

                report_doc = ReportDocument(
                    seq_number=item.get("seqNumber"),
                    doc_id=item.get("docID"),
                    edinet_code=item.get("edinetCode"),
                    sec_code=item.get("secCode"),
                    jcn=item.get("JCN"),
                    filer_name=item.get("filerName"),
                    fund_code=item.get("fundCode"),
                    ordinance_code=ordinance_code,
                    form_code=form_code,
                    doc_type_code=item.get("docTypeCode"),
                    period_start=item.get("periodStart"),
                    period_end=item.get("periodEnd"),
                    submit_date_time=submit_date_time,
                    doc_description=item.get("docDescription"),
                    issuer_edinet_code=item.get("issuerEdinetCode"),
                    subject_edinet_code=item.get("subjectEdinetCode"),
                    subsidiary_edinet_code=item.get("subsidiaryEdinetCode"),
                    current_report_reason=item.get("currentReportReason"),
                    parent_doc_id=item.get("parentDocID"),
                    ope_date_time=ope_date_time,
                    withdrawal_status=item.get("withdrawalStatus"),
                    doc_info_edit_status=item.get("docInfoEditStatus"),
                    disclosure_status=item.get("disclosureStatus"),
                    xbrl_flag=bool(item.get("xbrlFlag")),
                    pdf_flag=bool(item.get("pdfFlag")),
                    attach_doc_flag=bool(item.get("attachDocFlag")),
                    english_doc_flag=bool(item.get("englishDocFlag")),
                    csv_flag=bool(item.get("csvFlag")),
                    legal_status=item.get("legalStatus"),
                )
                report_doc_list.append(report_doc)
                logging.info(f"{day}, {report_doc}")
        return report_doc_list

    def _download_xbrl_in_zip(self, report_doc_list: list[ReportDocument]):
        """
        params.type:
            1: 提出本文書、監査報告書およびxbrl
            2: PDF
            3: 代替書面・添付文書
            4: 英文ファイル
            5: CSV
        """
        denominator = len(report_doc_list)
        for i, report_doc in enumerate(report_doc_list):
            doc_id = report_doc.doc_id
            logging.info(f"{doc_id}: {i + 1}/{denominator}")
            url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
            params = {
                "type": SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT,
                "Subscription-Key": os.environ.get("EDINET_API_KEY"),
            }
            filename = self.work_dir / f"{doc_id}.zip"
            res = requests.get(url, params=params, stream=True)

            if res.status_code == 200:
                with open(filename, "wb") as file:
                    for chunk in res.iter_content(chunk_size=1024):
                        file.write(chunk)

    def download_xbrl(self, request_data: RequestData) -> dict[str, ResponseData]:
        """
        Notes: 有価証券報告書の提出期限は原則として決算日から3ヵ月以内（3月末決算の企業であれば、同年6月中）
        """
        securities_report_list = self._extract(request_data)
        self._download_xbrl_in_zip(securities_report_list)
        logging.info("download finish")

        securities_report_dict = {}
        for x in securities_report_list:
            securities_report_dict[x.results[0].edinet_code] = x

        return securities_report_dict

    def _unzip_files_and_extract_xbrl(self) -> list[str]:
        """
        指定されたディレクトリ内のzipファイルを解凍し、指定したパターンに一致するXBRLファイルのリストを返します。
        xbrlファイルは各zipファイルに1つ、存在するようだ

        Returns:
            ['/path/to/extracted/file1.xbrl', '/path/to/extracted/file2.xbrl']
        """
        ZipFileService.extract_zip_files(self.work_dir, self.temp_dir)
        xbrl_files = list(self.temp_dir.glob("XBRL/PublicDoc/*.xbrl"))

        return [str(path) for path in xbrl_files]

    @staticmethod
    def _assign_attributes(counting_data: CountingData, facts):
        target_keys = {
            "EDINETCodeDEI": "edinet_code",
            "FilerNameInJapaneseDEI": "filer_name_jp",
            "AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees": "avg_salary",
            "AverageLengthOfServiceYearsInformationAboutReportingCompanyInformationAboutEmployees": "avg_tenure_years",
            "AverageLengthOfServiceMonthsInformationAboutReportingCompanyInformationAboutEmployees": "avg_tenure_months",  # noqa E501
            "AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees": "avg_age_years",
            "AverageAgeMonthsInformationAboutReportingCompanyInformationAboutEmployees": "avg_age_months",
            "NumberOfEmployees": "number_of_employees",
        }
        for fact in facts:
            key_to_set = target_keys.get(fact.concept.qname.localName)
            if key_to_set:
                setattr(counting_data, key_to_set, fact.value)
                if (
                    key_to_set == "number_of_employees"
                    and fact.contextID != "CurrentYearInstant_NonConsolidatedMember"
                ):
                    setattr(counting_data, "number_of_employees", None)
        return counting_data

    def make_counting_data(self) -> dict[str, CountingData]:
        counting_data_dict = {}
        for xbrl_path in self._unzip_files_and_extract_xbrl():
            counting_data = CountingData()
            ctrl = Cntlr.Cntlr()
            model_xbrl = ctrl.modelManager.load(xbrl_path)
            logging.info(f"{Path(xbrl_path).name}")
            counting_data = self._assign_attributes(counting_data, model_xbrl.facts)
            counting_data_dict[counting_data.edinet_code] = counting_data
        shutil.rmtree(self.temp_dir)
        return counting_data_dict

    def to_csv(self, data: list[CountingData], output_filename: str):
        all_companies = Company.objects.all()
        new_data = []
        for x in data:
            try:
                # If matching Company object is found, insert industry name to list
                company = all_companies.get(edinet_code=x.edinet_code)
                data_list = x.to_list()
                data_list.insert(2, company.submitter_industry)
            except ObjectDoesNotExist:
                # If no matching Company object is found, insert None
                data_list = x.to_list()
                data_list.insert(2, None)
            new_data.append(data_list)

        employee_frame = pd.DataFrame(
            data=new_data,
            columns=[
                "EDINETCODE",
                "企業名",
                "業種",
                "平均年間給与（円）",
                "平均勤続年数（年）",
                "平均年齢（歳）",
                "従業員数（人）",
            ],
        )
        employee_frame.to_csv(
            str(self.work_dir / output_filename), encoding="cp932", index=False
        )
        logging.info(f"{self.work_dir} に {output_filename} が出力されました")


if __name__ == "__main__":
    # 前提条件: EDINETコードリストのアップロード
    home_dir = os.path.expanduser("~")
    service = XbrlService(work_dir=Path(home_dir, "Downloads/xbrlReport"))
    doc_attr_dict = service.download_xbrl(
        RequestData(
            start_date=datetime.date(2022, 11, 1),
            end_date=datetime.date(2023, 10, 31),
        )
    )
    service.repository.delete_existing_records(list(doc_attr_dict.values()))
    service.repository.bulk_insert(doc_attr_dict, service.make_counting_data())
    logging.info("bulk_create finish")
