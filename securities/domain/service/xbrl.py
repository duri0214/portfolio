import datetime
import logging
import os
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import requests
from arelle import Cntlr

from securities.domain.repository.edinet import EdinetRepository
from securities.domain.valueobject.edinet import CountingData, RequestData, ResponseData

SUBMITTED_MAIN_DOCUMENTS_AND_AUDIT_REPORT = 1


class XbrlService:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.temp_dir = self.work_dir / "temp"
        self.repository = EdinetRepository()

    @staticmethod
    def _make_doc_id_list(request_data: RequestData) -> list[str]:
        def _process_results_data(results: list) -> list[str]:
            """
            有価証券報告書: ordinanceCode == "010" and formCode =="030000"
            訂正有価証券報告書: ordinanceCode == "010" and formCode =="030001"
            """
            doc_id_list = []
            for result in results:
                if result.ordinance_code == "010" and result.form_code == "030000":
                    doc_id_list.append(result.doc_id)
            return doc_id_list

        securities_report_doc_list = []
        for _, day in enumerate(request_data.day_list):
            url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
            params = {
                "date": day,
                "type": request_data.SECURITIES_REPORT_AND_META_DATA,
                "Subscription-Key": os.environ.get("EDINET_API_KEY"),
            }
            res = requests.get(url, params=params)
            res.raise_for_status()
            response_data = ResponseData(res.json())
            securities_report_doc_list.extend(
                _process_results_data(response_data.results)
            )
        return securities_report_doc_list

    def _download_xbrl_in_zip(self, securities_report_doc_list):
        """
        params.type:
            1: 提出本文書、監査報告書およびxbrl
            2: PDF
            3: 代替書面・添付文書
            4: 英文ファイル
            5: CSV
        """
        denominator = len(securities_report_doc_list)
        for i, doc_id in enumerate(securities_report_doc_list):
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

    def download_xbrl(self):
        """
        Notes: 有価証券報告書の提出期限は原則として決算日から3ヵ月以内（3月末決算の企業であれば、同年6月中）
        """
        request_data = RequestData(
            start_date=datetime.date(2023, 11, 1),
            end_date=datetime.date(2023, 11, 9),
        )
        securities_report_doc_list = list(set(self._make_doc_id_list(request_data)))
        logging.info(f"number of lists：{len(securities_report_doc_list)}")
        logging.info(f"securities report doc list：{securities_report_doc_list}")

        self._download_xbrl_in_zip(securities_report_doc_list)
        logging.info("download finish")

    def _unzip_files_and_extract_xbrl(self) -> list[str]:
        """
        指定されたディレクトリ内のzipファイルを解凍し、指定したパターンに一致するXBRLファイルのリストを返します。
        xbrlファイルは各zipファイルに1つ、存在するようだ

        使用例:
            >> obj = XbrlService()
            >> result = obj.unzip_files_and_extract_xbrl('/path/to/zip/directory', '*.xbrl')
            >> print(result)
            ['/path/to/extracted/file1.xbrl', '/path/to/extracted/file2.xbrl']
        """

        zip_files = list(self.work_dir.glob("*.zip"))
        logging.info(f"number of zip files: {len(zip_files)}")
        for _, zip_file in enumerate(zip_files, start=1):
            with zipfile.ZipFile(str(zip_file), "r") as zipf:
                zipf.extractall(str(self.temp_dir))
        xbrl_files = list(self.work_dir.glob("**/XBRL/PublicDoc/*.xbrl"))

        return [str(path) for path in xbrl_files]

    def _assign_attributes(self, counting_data: CountingData, facts):
        target_keys = {
            "EDINETCodeDEI": "edinet_code",
            "FilerNameInJapaneseDEI": "filer_name_jp",
            "AverageAnnualSalaryInformationAboutReportingCompanyInformationAboutEmployees": "salary_info",
            "AverageLengthOfServiceYearsInformationAboutReportingCompanyInformationAboutEmployees": "service_years",
            "AverageLengthOfServiceMonthsInformationAboutReportingCompanyInformationAboutEmployees": "service_months",
            "AverageAgeYearsInformationAboutReportingCompanyInformationAboutEmployees": "age_years",
            "AverageAgeMonthsInformationAboutReportingCompanyInformationAboutEmployees": "age_months",
            "NumberOfEmployees": "number_of_employees",
        }
        for fact in facts:
            key_to_set = target_keys.get(fact.concept.qname.localName)
            if key_to_set:
                setattr(counting_data, key_to_set, fact.value)
                if key_to_set == "edinet_code":
                    counting_data.industry_name = self.repository.get_industry_name(
                        counting_data.edinet_code
                    )
                elif (
                    key_to_set == "number_of_employees"
                    and fact.contextID != "CurrentYearInstant_NonConsolidatedMember"
                ):
                    setattr(counting_data, "number_of_employees", None)
        return counting_data

    def make_counting_data(self) -> list[CountingData]:
        counting_list = []
        for _, xbrl_path in enumerate(self._unzip_files_and_extract_xbrl()):
            counting_data = CountingData()
            ctrl = Cntlr.Cntlr()
            model_xbrl = ctrl.modelManager.load(xbrl_path)
            logging.info(f"{Path(xbrl_path).name}")
            counting_data = self._assign_attributes(counting_data, model_xbrl.facts)
            counting_list.append(counting_data)
        shutil.rmtree(self.temp_dir)
        return counting_list

    def to_csv(self, data: list[CountingData], output_filename: str):
        employee_frame = pd.DataFrame(
            data=[x.to_list() for x in data],
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
        employee_frame.to_csv(str(self.work_dir / output_filename), encoding="cp932")
        logging.info(f"{self.work_dir} に {output_filename} が出力されました")


if __name__ == "__main__":
    # 前提条件: EDINETコードリストのアップロード
    home_dir = os.path.expanduser("~")
    service = XbrlService(work_dir=Path(home_dir, "Downloads/xbrlReport"))
    service.download_xbrl()
    service.to_csv(
        data=service.make_counting_data(),
        output_filename="output.csv",
    )
