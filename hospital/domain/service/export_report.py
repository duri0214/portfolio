import os
import uuid
from itertools import islice, groupby
from pathlib import Path
from urllib.parse import quote

from django.http import HttpResponse
from openpyxl.reader.excel import load_workbook
from openpyxl.worksheet.copier import WorksheetCopy

from hospital.domain.valueobject.export_report import BillingListRow
from hospital.models import ElectionLedger


class ExportBillingService:
    def __init__(self, temp_folder: Path):
        self.temp_folder = temp_folder
        os.makedirs(self.temp_folder, exist_ok=True)

    def create_unique_filename(self):
        return str(self.temp_folder / f"{str(uuid.uuid4())}.xlsx")

    def get_excel_data(self, filename: str) -> bytes:
        with open(self.temp_folder / filename, "rb") as f:
            return f.read()

    def export(self, election_id) -> HttpResponse:
        ledgers = (
            ElectionLedger.objects.filter(election_id=election_id)
            .select_related("vote_ward")
            .order_by("vote_ward__name")
        )

        filepath = os.path.abspath("hospital/domain/service/xlsx/billing_list.xlsx")
        wb = load_workbook(filepath)
        filename = self.create_unique_filename()

        for ward_name, group in groupby(ledgers, key=lambda x: x.vote_ward.name):
            sh_template = wb["ひな形"]

            ledgers_iter = iter(group)
            chunk_size = 15
            while True:
                chunk = list(islice(ledgers_iter, chunk_size))
                if not chunk:
                    break

                if "data" in wb.sheetnames:
                    del wb["data"]
                sh_data = wb.create_sheet("data")
                sh_data.append(BillingListRow.get_field_names())

                for ledger in chunk:
                    row = BillingListRow(ledger)
                    sh_data.append(row.to_list())

                sequence_number = str(wb.sheetnames.count(ward_name))
                new_worksheet = wb.copy_worksheet(sh_template)
                new_worksheet.title = ward_name + sequence_number

                # value copy
                copier = WorksheetCopy(sh_template, new_worksheet)
                copier.copy_worksheet()

        del wb["ひな形"]
        del wb["data"]
        wb.save(filename)

        try:
            excel_data = self.get_excel_data(filename)

            response = HttpResponse(
                excel_data,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            header_content = f"attachment; filename*=UTF-8''{quote("請求者名簿.xlsx")}"
            response["Content-Disposition"] = header_content
        finally:
            os.remove(self.temp_folder / filename)
        return response
