import os
import uuid
from pathlib import Path

from django.http import HttpResponse
from openpyxl import Workbook

from hospital.domain.valueobject.export_report import DataRow
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
        ledgers = ElectionLedger.objects.filter(election_id=election_id)

        wb = Workbook()
        ws = wb.active
        ws.append([field.name for field in ElectionLedger._meta.fields])

        filename = self.create_unique_filename()

        for ledger in ledgers:
            data_row = DataRow(fields=ledger._meta.fields, instance=ledger)
            ws.append(data_row.to_list())
        wb.save(filename=filename)

        try:
            excel_data = self.get_excel_data(filename)

            response = HttpResponse(
                excel_data,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=ElectionLedger.xlsx"
        finally:
            os.remove(self.temp_folder / filename)
        return response
