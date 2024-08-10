from django.core.management.base import BaseCommand

from securities.models import ReportDocument


class Command(BaseCommand):
    help = "Download edinet data"

    def handle(self, *args, **options):
        # 処理対象
        report_documents = ReportDocument.objects.filter(download_reserved=True)[:20]

        # edinet_list = []
        # for _, row in df.iterrows():
        #     edinet_list.append(
        #         Company(
        #             edinet_code=na(row["ＥＤＩＮＥＴコード"]),
        #             type_of_submitter=na(row["提出者種別"]),
        #             listing_status=na(row["上場区分"]),
        #             consolidated_status=na(row["連結の有無"]),
        #             capital=(int(row["資本金"]) if pd.notna(row["資本金"]) else None),
        #             end_fiscal_year=na(row["決算日"]),
        #             submitter_name=na(row["提出者名"]),
        #             submitter_name_en=na(row["提出者名（英字）"]),
        #             submitter_name_kana=na(row["提出者名（ヨミ）"]),
        #             address=na(row["所在地"]),
        #             submitter_industry=na(row["提出者業種"]),
        #             securities_code=na(row["証券コード"]),
        #             corporate_number=na(row["提出者法人番号"]),
        #         )
        #     )
        # Company.objects.bulk_create(edinet_list)

        # 処理対象のフラグを落とす
        ReportDocument.objects.filter(
            id__in=[report_document.id for report_document in report_documents]
        ).update(download_reserved=False)

        self.stdout.write(self.style.SUCCESS("Successfully download edinet data"))
