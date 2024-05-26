import zipfile
from pathlib import Path

import pandas as pd
from arelle import Cntlr, ModelManager

from securities.domain.valueobject.edinet import Company, EdinetIndustry
from securities.models import Edinet


class XbrlService:
    def __init__(
        self,
        zip_dir: Path,
    ):
        xbrl_file_expressions = zip_dir / "XBRL" / "PublicDoc" / "*.xbrl"
        xbrl_files = self._unzip_files_and_extract_xbrl(
            zip_dir, str(xbrl_file_expressions)
        )
        self.edinet_industry_list = self._get_edinet_industry_list()
        self.edinet_company_info_list = self._make_edinet_company_info_list(xbrl_files)

    @staticmethod
    def _unzip_files_and_extract_xbrl(
        zip_directory: Path, xbrl_file_expressions: str
    ) -> list[str]:
        """
        指定されたディレクトリ内のzipファイルを解凍し、指定したパターンに一致するXBRLファイルのリストを返します。

        引数:
            zip_directory (str): 解凍するZIPファイルが含まれるディレクトリ。
            xbrl_file_expressions (str): 抽出後のXBRLファイルとマッチさせるためのファイル表現パターン。

        戻り値:
            list[str]: 表現パターンにマッチする抽出したXBRLファイルのリスト。

        使用例:
            >> obj = XbrlService()
            >> result = obj.unzip_files_and_extract_xbrl('/path/to/zip/directory', '*.xbrl')
            >> print(result)
            ['/path/to/extracted/file1.xbrl', '/path/to/extracted/file2.xbrl']
        """

        def _log_progress(current: str, total: int, zip_files_count: int):
            print(f"{current} : {total} / {zip_files_count}")

        zip_files = list(zip_directory.glob("*.zip"))
        print("number_of_zip_files：", len(zip_files))

        for index, zip_file in enumerate(zip_files, start=1):
            _log_progress(zip_file.name, index, len(zip_files))
            with zipfile.ZipFile(str(zip_file), "r") as zipf:
                zipf.extractall(str(zip_directory))

        xbrl_files = list(zip_directory.glob(xbrl_file_expressions))
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

    def _make_edinet_company_info_list(self, xbrl_files: list[str]):
        def _calculate_years(years: str, months: str) -> str:
            """
            このヘルパー関数は、現在の「年数」および「月数」を文字列として受け取り、
            その月数を小数点付きの年数に変換し、それを年数に加えます。そして結果を文字列として返します
            """
            if len(months) != 0:
                years_decimal = round(int(months) / 12, 1)
                years_final = int(years) + years_decimal
                years_final = str(years_final)
                return years_final
            return years

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
        edinet_company_info_list = []
        for index, xbrl_file in enumerate(xbrl_files):
            company_list = []  # 企業情報
            company = Company()
            model_xbrl = ModelManager.initialize(Cntlr.Cntlr()).load(xbrl_file)
            print(xbrl_file, ":", index + 1, "/", len(xbrl_files))
            for fact in model_xbrl.facts:
                key_to_set = target_keys.get(fact.concept.qname.localName)
                if key_to_set:
                    setattr(company, key_to_set, fact.value)
                    # キーが 'edinet_code' の場合、業種名も取得します
                    if key_to_set == "edinet_code":
                        company.industry_name = self._get_industry_name(
                            company.edinet_code
                        )
                    # キーが 'number_of_employees' だが、contextID が CurrentYear でない場合、値を設定すべきではありません
                    elif (
                        key_to_set == "number_of_employees"
                        and fact.contextID != "CurrentYearInstant_NonConsolidatedMember"
                    ):
                        setattr(company, "number_of_employees", None)
            company_list.append(company)

        return edinet_company_info_list

    def to_csv(self, output_csv_filepath: Path):
        employee_frame = pd.DataFrame(
            data=self.edinet_company_info_list,
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
        print(employee_frame)
        employee_frame.to_csv(str(output_csv_filepath), encoding="cp932")


if __name__ == "__main__":
    # edinet_code_dl_info_filepath: ダウンロードしたEDINETコードリストを読み込むための格納フォルダ
    #  https://disclosure2.edinet-fsa.go.jp/weee0010.aspx から EDINETコードリストをダウンロード
    # zip_dir: EDINET APIで取得してきたzipファイルを格納するフォルダ
    base_folder = Path("C:/Users/yoshi/Downloads/xbrlReport")
    service = XbrlService(zip_dir=base_folder / "SR")
    service.to_csv(output_csv_filepath=Path("./xbrl_qiita.csv"))

    print("extract finish")
