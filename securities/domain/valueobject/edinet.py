import datetime
from dataclasses import dataclass


@dataclass
class RequestData:
    SECURITIES_REPORT_AND_META_DATA = 2
    start_date: datetime.date
    end_date: datetime.date

    def __post_init__(self):
        self.doc_type = self.SECURITIES_REPORT_AND_META_DATA

        # Calculate day_list
        period = self.end_date - self.start_date
        self.day_list = []
        for d in range(int(period.days)):
            day = self.start_date + datetime.timedelta(days=d)
            self.day_list.append(day)
        self.day_list.append(self.end_date)


class ResponseData:
    class _Metadata:
        class _Parameter:
            def __init__(self, data: dict) -> None:
                self.date = data.get("date")
                self.type = data.get("type")

        class _ResultSet:
            def __init__(self, data: dict) -> None:
                self.count = data.get("count")

        def __init__(self, data: dict) -> None:
            self.title = data.get("title")
            self.parameter = self._Parameter(data.get("parameter"))
            self.result_set = self._ResultSet(data.get("resultset"))
            self.process_date_time = data.get("processDateTime")
            self.status = data.get("status")
            self.message = data.get("message")

    class _Result:
        def __init__(self, data):
            self.seq_number = data.get("seqNumber")
            self.doc_id = data.get("docID")
            self.edinet_code = data.get("edinetCode")
            self.sec_code = data.get("secCode")
            self.jcn = data.get("JCN")
            self.filer_name = data.get("filerName")
            self.fund_code = data.get("fundCode")
            self.ordinance_code = data.get("ordinanceCode")
            self.form_code = data.get("formCode")
            self.doc_type_code = data.get("docTypeCode")
            self.period_start = data.get("periodStart")
            self.period_end = data.get("periodEnd")
            self.submit_date_time = data.get("submitDateTime")
            self.doc_description = data.get("docDescription")
            self.issuer_edinet_code = data.get("issuerEdinetCode")
            self.subject_edinet_code = data.get("subjectEdinetCode")
            self.subsidiary_edinet_code = data.get("subsidiaryEdinetCode")
            self.current_report_reason = data.get("currentReportReason")
            self.parent_doc_id = data.get("parentDocID")
            self.ope_date_time = data.get("opeDateTime")
            self.withdrawal_status = data.get("withdrawalStatus")
            self.doc_info_edit_status = data.get("docInfoEditStatus")
            self.disclosure_status = data.get("disclosureStatus")
            self.xbrl_flag = data.get("xbrlFlag")
            self.pdf_flag = data.get("pdfFlag")
            self.attach_doc_flag = data.get("attachDocFlag")
            self.english_doc_flag = data.get("englishDocFlag")
            self.csv_flag = data.get("csvFlag")
            self.legal_status = data.get("legalStatus")

    def __init__(self, data):
        self.metadata = self._Metadata(data.get("metadata"))
        self.results = [self._Result(item) for item in data.get("results", [])]


@dataclass
class Company:
    edinet_code: str | None = None
    filer_name_jp: str | None = None
    industry_name: str | None = None
    salary_info: str | None = None
    service_years: str | None = None
    service_months: str | None = None
    age_years: str | None = None
    age_months: str | None = None
    number_of_employees: str | None = None

    @property
    def service_years_combined(self) -> str | None:
        if self.service_months:
            service_years_decimal = round(int(self.service_months) / 12, 1)
            service_years = int(self.service_years) + service_years_decimal
            return str(service_years)
        return self.service_years

    @property
    def age_years_combined(self) -> str | None:
        if self.age_months:
            age_years_decimal = round(int(self.age_months) / 12, 1)
            age_years = int(self.age_years) + age_years_decimal
            return str(age_years)
        return self.age_years

    def to_list(self) -> list[str | None]:
        return [
            self.edinet_code,
            self.filer_name_jp,
            self.industry_name,
            self.salary_info,
            self.service_years_combined,
            self.age_years_combined,
            self.number_of_employees,
        ]
