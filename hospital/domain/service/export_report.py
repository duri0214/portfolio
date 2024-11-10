import os
import uuid
from abc import ABC, abstractmethod
from itertools import islice, groupby
from pathlib import Path
from urllib.parse import quote

from django.http import HttpResponse
from openpyxl.reader.excel import load_workbook

from config.settings import BASE_DIR
from hospital.domain.valueobject.export_report import BillingListRow
from hospital.models import ElectionLedger


class AbstractExport(ABC):
    def __init__(self, temp_folder: Path):
        self.temp_folder = temp_folder
        os.makedirs(self.temp_folder, exist_ok=True)

    def create_unique_filename(self):
        return str(self.temp_folder / f"{str(uuid.uuid4())}.xlsx")

    def get_excel_data(self, filename: str) -> bytes:
        with open(self.temp_folder / filename, "rb") as f:
            return f.read()

    @abstractmethod
    def export(self, *args, **kwargs):
        pass


class ExportBillingService(AbstractExport):
    def export(self, election_id) -> HttpResponse:
        ledgers = (
            ElectionLedger.objects.filter(election_id=election_id)
            .select_related("vote_ward")
            .order_by("vote_ward__name")
        )

        wb = load_workbook(BASE_DIR / "hospital/domain/service/xlsx/billing_list.xlsx")
        filename = self.create_unique_filename()

        chunk_size = 15
        start_row = 5

        for ward_name, group in groupby(ledgers, key=lambda x: x.vote_ward.name):
            sheet_counter = 1
            ledgers_iter = iter(group)
            while True:
                chunk = list(islice(ledgers_iter, chunk_size))
                if not chunk:
                    break

                new_worksheet = wb.copy_worksheet(wb["ひな形"])
                new_worksheet.title = ward_name if sheet_counter == 1 else f"{ward_name} ({sheet_counter})"
                sheet_counter += 1

                for i, ledger in enumerate(chunk, start=0):
                    row = BillingListRow(ledger)
                    new_worksheet.cell(row=start_row + i, column=1, value=row.address)  # A列
                    new_worksheet.cell(row=start_row + i, column=2, value=row.voter_name)  # B列
                    new_worksheet.cell(row=start_row + i, column=3, value=row.date_of_birth)  # C列
        del wb["ひな形"]
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
