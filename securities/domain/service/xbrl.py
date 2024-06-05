import datetime
import logging
import os
import shutil
from pathlib import Path

import pandas as pd
import requests
from arelle import Cntlr
from django.core.exceptions import ObjectDoesNotExist

from lib.zipfileservice import ZipFileService
from securities.domain.repository.edinet import EdinetRepository
from securities.domain.valueobject.edinet import CountingData, RequestData, ResponseData
from securities.models import Company

SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT = 1


class XbrlService:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.temp_dir = self.work_dir / "temp"
        self.repository = EdinetRepository()

    @staticmethod
    def _extract(request_data: RequestData) -> list[ResponseData]:
        """
        特定の提出書類をもつ ResponseData を抽出する（重複した doc_id は除外される）
         有価証券報告書: ordinanceCode == "010" and formCode =="030000"
         訂正有価証券報告書: ordinanceCode == "010" and formCode =="030001"
        """
        securities_report_dict = {}
        for day in request_data.day_list:
            url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
            params = {
                "date": day,
                "type": request_data.SECURITIES_REPORT_AND_META_DATA,
                "Subscription-Key": os.environ.get("EDINET_API_KEY"),
            }
            res = requests.get(url, params=params)
            res.raise_for_status()
            response_data = ResponseData(res.json())
            for result in response_data.results:
                if result.ordinance_code == "010" and result.form_code == "030000":
                    logging.info(
                        f"{day}, {result.filer_name}, "
                        f"edinet_code: {result.edinet_code}, "
                        f"doc_id: {result.doc_id}, "
                        f"期間（自）: {response_data.results[0].period_start}, "
                        f"期間（至）: {response_data.results[0].period_end}, "
                    )
                    response_data.results = [result]
            if (
                response_data.results
                and response_data.results[0].doc_id not in securities_report_dict
            ):
                securities_report_dict[response_data.results[0].doc_id] = response_data
        return list(securities_report_dict.values())

    def _download_xbrl_in_zip(self, securities_report_list: list[ResponseData]):
        """
        params.type:
            1: 提出本文書、監査報告書およびxbrl
            2: PDF
            3: 代替書面・添付文書
            4: 英文ファイル
            5: CSV
        """
        denominator = len(securities_report_list)
        for i, securities_report in enumerate(securities_report_list):
            doc_id = securities_report.results[0].doc_id
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

    def make_counting_data(self) -> list[CountingData]:
        counting_list = []
        for xbrl_path in self._unzip_files_and_extract_xbrl():
            counting_data = CountingData()
            ctrl = Cntlr.Cntlr()
            model_xbrl = ctrl.modelManager.load(xbrl_path)
            logging.info(f"{Path(xbrl_path).name}")
            counting_data = self._assign_attributes(counting_data, model_xbrl.facts)
            counting_list.append(counting_data)
        shutil.rmtree(self.temp_dir)
        return counting_list

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
            start_date=datetime.date(2023, 11, 1),
            end_date=datetime.date(2023, 11, 29),
        )
    )
    service.repository.delete_existing_records(list(doc_attr_dict.values()))
    service.repository.bulk_insert(doc_attr_dict, service.make_counting_data())
    logging.info("bulk_create finish")
