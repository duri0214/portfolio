import os
import shutil
import zipfile
from pathlib import Path

import pandas as pd
from arelle import Cntlr, ModelManager

from securities.domain.valueobject.edinet import Company, EdinetIndustry
from securities.models import Edinet


class XbrlService:
    def __init__(self, zip_dir: Path):
        xbrl_files = self._unzip_files_and_extract_xbrl(zip_dir)
        self.edinet_industry_list = self._get_edinet_industry_list()
        self.edinet_company_list = self._make_edinet_company_list(xbrl_files)

    @staticmethod
    def _unzip_files_and_extract_xbrl(zip_directory: Path) -> list[str]:
        """
        指定されたディレクトリ内のzipファイルを解凍し、指定したパターンに一致するXBRLファイルのリストを返します。
        xbrlファイルは各zipファイルに1つ、存在するようだ

        引数:
            zip_directory (str): 解凍するZIPファイルが含まれるディレクトリ。

        戻り値:
            list[str]: 表現パターンにマッチする抽出したXBRLファイルのリスト。

        使用例:
            >> obj = XbrlService()
            >> result = obj.unzip_files_and_extract_xbrl('/path/to/zip/directory', '*.xbrl')
            >> print(result)
            ['/path/to/extracted/file1.xbrl', '/path/to/extracted/file2.xbrl']
        """

        zip_files = list(zip_directory.glob("*.zip"))
        print("number of zip files: ", len(zip_files))
        temp_dir = zip_directory / "temp"
        for index, zip_file in enumerate(zip_files, start=1):
            with zipfile.ZipFile(str(zip_file), "r") as zipf:
                zipf.extractall(str(temp_dir))
        xbrl_files = list(zip_directory.glob("**/XBRL/PublicDoc/*.xbrl"))
        shutil.rmtree(temp_dir)

        return [str(path) for path in xbrl_files]

    @staticmethod
    def _get_edinet_industry_list() -> list[EdinetIndustry]:
        return [
            EdinetIndustry(
                edinet_code=edinet.edinet_code,
                industry_name=edinet.submitter_industry,
            )
            for edinet in Edinet.objects.all()
        ]

    def _get_industry_name(self, edinet_code: str) -> str | None:
        for edinet_industry in self.edinet_industry_list:
            if edinet_industry.edinet_code == edinet_code:
                return edinet_industry.industry_name
        return None

    def _make_edinet_company_list(self, xbrl_files: list[str]) -> list[Company]:
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
        edinet_company_list = []
        for index, xbrl_file in enumerate(xbrl_files):
            company = Company()
            model_xbrl = ModelManager.initialize(Cntlr.Cntlr()).load(xbrl_file)
            print(f"{Path(xbrl_file).name}")
            print(f"  model_xbrl.facts: {model_xbrl.facts}")
            for fact in model_xbrl.facts:
                print(fact)
                key_to_set = target_keys.get(fact.concept.qname.localName)
                print(f"  {key_to_set}...")
                if key_to_set:
                    setattr(company, key_to_set, fact.value)
                    # キーが 'edinet_code' の場合、業種名も取得します
                    if key_to_set == "edinet_code":
                        company.industry_name = self._get_industry_name(
                            company.edinet_code
                        )
                    # キーが 'number_of_employees' だが、contextID が CurrentYear でない場合、値を設定しない
                    elif (
                        key_to_set == "number_of_employees"
                        and fact.contextID != "CurrentYearInstant_NonConsolidatedMember"
                    ):
                        setattr(company, "number_of_employees", None)
            edinet_company_list.append(company)

        return edinet_company_list

    def to_csv(self, output_csv_filepath: Path):
        employee_frame = pd.DataFrame(
            data=[x.to_list() for x in self.edinet_company_list],
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
        employee_frame.to_csv(str(output_csv_filepath), encoding="cp932")


if __name__ == "__main__":
    # edinet_code_dl_info_filepath: ダウンロードしたEDINETコードリストを読み込むための格納フォルダ
    #  https://disclosure2.edinet-fsa.go.jp/weee0010.aspx から EDINETコードリストをダウンロード
    # zip_dir: EDINET APIで取得してきたzipファイルを格納するフォルダ
    home_dir = os.path.expanduser("~")
    work_dir = Path(home_dir, "Downloads/xbrlReport")
    service = XbrlService(zip_dir=work_dir)
    service.to_csv(output_csv_filepath=work_dir / "output.csv")

    print("extract finish")
