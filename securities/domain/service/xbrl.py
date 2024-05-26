import os
import shutil
import zipfile
from pathlib import Path

import pandas as pd
from arelle import Cntlr, ModelManager

from securities.domain.repository.edinet.edinet_repository import EdinetRepository
from securities.domain.valueobject.edinet import Company


class XbrlService:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.repository = EdinetRepository()

    def download_xbrl(self):
        pass

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
        print("number of zip files: ", len(zip_files))
        temp_dir = self.work_dir / "temp"
        for index, zip_file in enumerate(zip_files, start=1):
            with zipfile.ZipFile(str(zip_file), "r") as zipf:
                zipf.extractall(str(temp_dir))
        xbrl_files = list(self.work_dir.glob("**/XBRL/PublicDoc/*.xbrl"))
        shutil.rmtree(temp_dir)

        return [str(path) for path in xbrl_files]

    def _assign_attributes(self, company: Company, facts):
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
                setattr(company, key_to_set, fact.value)
                if key_to_set == "edinet_code":
                    company.industry_name = self.repository.get_industry_name(
                        company.edinet_code
                    )
                elif (
                    key_to_set == "number_of_employees"
                    and fact.contextID != "CurrentYearInstant_NonConsolidatedMember"
                ):
                    setattr(company, "number_of_employees", None)
        return company

    def make_edinet_company_data(self) -> list[Company]:
        company_list = []
        for index, xbrl_path in enumerate(self._unzip_files_and_extract_xbrl()):
            company = Company()
            model_xbrl = ModelManager.initialize(Cntlr.Cntlr()).load(xbrl_path)
            print(f"{Path(xbrl_path).name}")
            print(f"  model_xbrl.facts: {model_xbrl.facts}")
            company = self._assign_attributes(company, model_xbrl.facts)
            company_list.append(company)
        return company_list

    def to_csv(self, data: list[Company], output_filename: str):
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
        print("\n", employee_frame)
        employee_frame.to_csv(str(self.work_dir / output_filename), encoding="cp932")


if __name__ == "__main__":
    # 前提条件: EDINETコードリストのアップロード
    home_dir = os.path.expanduser("~")
    service = XbrlService(work_dir=Path(home_dir, "Downloads/xbrlReport"))
    service.download_xbrl()
    service.to_csv(
        data=service.make_edinet_company_data(),
        output_filename="output.csv",
    )

    print("extract finish")
