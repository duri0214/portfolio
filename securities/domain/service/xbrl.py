import datetime
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import requests
from arelle import Cntlr
from django.utils import timezone

from lib.zipfileservice import ZipFileService
from securities.domain.repository.edinet import EdinetRepository
from securities.domain.valueobject.edinet import CountingData, RequestData
from securities.models import ReportDocument

SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT = 1


class XbrlService:
    def __init__(self):
        self.repository = EdinetRepository()

    @staticmethod
    def fetch_report_doc_list(request_data: RequestData) -> list[ReportDocument]:
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

    def download_xbrl(self, doc_id: str, work_dir: Path) -> ReportDocument:
        """
        Notes: 有価証券報告書の提出期限は原則として決算日から3ヵ月以内（3月末決算の企業であれば、同年6月中）
        """
        report_doc = self.repository.find_by_doc_id(doc_id)

        logging.info(f"{report_doc.doc_id} をダウンロード中...")
        url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{report_doc.doc_id}"
        params = {
            "type": SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT,
            "Subscription-Key": os.environ.get("EDINET_API_KEY"),
        }
        filename = work_dir / f"{report_doc.doc_id}.zip"
        res = requests.get(url, params=params, stream=True)
        res.raise_for_status()

        with open(filename, "wb") as file:
            for chunk in res.iter_content(chunk_size=1024):
                file.write(chunk)
        logging.info(f"{report_doc.doc_id} をダウンロード完了")

        return report_doc

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

    def make_counting_data(self, work_dir: Path, temp_dir: Path) -> CountingData:
        ZipFileService.extract_zip_files(work_dir, temp_dir)
        xbrl_path = str(next(temp_dir.glob("XBRL/PublicDoc/*.xbrl")))

        ctrl = Cntlr.Cntlr()
        model_xbrl = ctrl.modelManager.load(xbrl_path)
        logging.info(f"  xbrl: {Path(xbrl_path).name}")
        counting_data = self._assign_attributes(
            counting_data=CountingData(), facts=model_xbrl.facts
        )
        shutil.rmtree(work_dir)
        return counting_data
