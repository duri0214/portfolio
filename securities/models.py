from django.db import models


class ReportDocument(models.Model):
    """
    提出書類一覧APIで返ってくる顔ぶれデータ

    Attributes:
        seq_number (models.SmallIntegerField): The sequence number of the document.
        doc_id (models.CharField): The document's management number.
        edinet_code (models.CharField): The submitter EDINET code.
        sec_code (models.CharField): The submitter security code (nullable).
        jcn (models.CharField): The submitter corporate number (nullable).
        filer_name (models.CharField): The name of the submitter.
        fund_code (models.CharField): The fund code associated with the document (nullable).
        ordinance_code (models.CharField): The ordinance code of the document.
        form_code (models.CharField): The code representing the document's form.
        doc_type_code (models.CharField): The code representing the document type.
        period_start (models.DateField): The start date of the period covered by the document.
        period_end (models.DateField): The end date of the period covered by the document.
        submit_date_time (models.DateTimeField): The date and time when the document was submitted.
        doc_description (models.CharField): A brief description of the document.
        issuer_edinet_code (models.CharField): The EDINET code of the issuing company (nullable).
        subject_edinet_code (models.CharField): The EDINET code of the subject (nullable).
        subsidiary_edinet_code (models.CharField): The EDINET code of the subsidiary (nullable).
        current_report_reason (models.TextField): The reason for submitting a current report (nullable).
        parent_doc_id (models.CharField): The management number of the parent document (nullable).
        ope_date_time (models.DateTimeField): The date and time when the document was operated (nullable).
        withdrawal_status (models.CharField): The withdrawal status of the document.
        doc_info_edit_status (models.CharField): The modification status of the document information.
        disclosure_status (models.CharField): The disclosure status of the document.
        xbrl_flag (models.BooleanField): A flag indicating whether the document has an XBRL file.
        pdf_flag (models.BooleanField): A flag indicating whether the document has a PDF file.
        attach_doc_flag (models.BooleanField): A flag indicating whether the document has an attached document.
        english_doc_flag (models.BooleanField): A flag indicating whether the document has an English file.
        csv_flag (models.BooleanField): A flag indicating whether the document has a CSV file.
        legal_status (models.BooleanField): A flag indicating whether the document is vertical reading.
        created_at (models.DateTimeField): The date and time when the document was created.
        updated_at (models.DateTimeField): The date and time when the document was last updated.
    """

    seq_number = models.SmallIntegerField(verbose_name="連番")
    doc_id = models.CharField(verbose_name="書類管理番号", max_length=8)
    edinet_code = models.CharField(verbose_name="提出者EDINETコード", max_length=6)
    sec_code = models.CharField(
        verbose_name="提出者証券コード", max_length=5, null=True
    )
    jcn = models.CharField(verbose_name="提出者法人番号", max_length=13, null=True)
    filer_name = models.CharField(verbose_name="提出者名", max_length=128)
    fund_code = models.CharField(verbose_name="ファンドコード", max_length=6, null=True)
    ordinance_code = models.CharField(verbose_name="府令コード", max_length=3)
    form_code = models.CharField(verbose_name="様式コード", max_length=6)
    doc_type_code = models.CharField(verbose_name="書類種別コード", max_length=3)
    period_start = models.DateField(verbose_name="期間（自）")
    period_end = models.DateField(verbose_name="期間（至）")
    submit_date_time = models.DateTimeField(verbose_name="提出日時")
    doc_description = models.CharField(verbose_name="提出書類概要", max_length=147)
    issuer_edinet_code = models.CharField(
        verbose_name="発行会社EDINETコード", max_length=6, null=True
    )
    subject_edinet_code = models.CharField(
        verbose_name="対象EDINETコード", max_length=6, null=True
    )
    subsidiary_edinet_code = models.CharField(
        verbose_name="子会社EDINETコード", max_length=69, null=True
    )
    current_report_reason = models.TextField(verbose_name="臨報提出事由", null=True)
    parent_doc_id = models.CharField(
        verbose_name="親書類管理番号", max_length=8, null=True
    )
    ope_date_time = models.DateTimeField(verbose_name="操作日時", null=True)
    withdrawal_status = models.CharField(verbose_name="取下区分", max_length=1)
    doc_info_edit_status = models.CharField(
        verbose_name="書類情報修正区分", max_length=1
    )
    disclosure_status = models.CharField(verbose_name="開示不開示区分", max_length=1)
    xbrl_flag = models.BooleanField(verbose_name="XBRL有無フラグ")
    pdf_flag = models.BooleanField(verbose_name="PDF有無フラグ")
    attach_doc_flag = models.BooleanField(verbose_name="代替書面・添付文書有無フラグ")
    english_doc_flag = models.BooleanField(verbose_name="英文ファイル有無フラグ")
    csv_flag = models.BooleanField(verbose_name="CSV有無フラグ")
    legal_status = models.BooleanField(verbose_name="縦覧区分")
    download_reserved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.doc_id} - {self.edinet_code}"


class Company(models.Model):
    """
    提出書類一覧APIで返ってくる顔ぶれから書類を取得してできあがる、企業マスタ

    Attributes:
        edinet_code (CharField): The EDINET code of the company.
        type_of_submitter (CharField): The type of submitter of the company.
        listing_status (CharField): The listing status of the company.
        consolidated_status (CharField): The consolidated status of the company.
        capital (IntegerField): The capital of the company.
        end_fiscal_year (CharField): The end fiscal year of the company.
        submitter_name (CharField): The name of the submitter of the company.
        submitter_name_en (CharField): The name of the submitter in English.
        submitter_name_kana (CharField): The name of the submitter in Kana.
        address (CharField): The address of the company.
        submitter_industry (CharField): The industry of the submitter.
        securities_code (CharField): The securities code of the company.
        corporate_number (CharField): The corporate number of the submitter.
        created_at (DateTimeField): The timestamp when the company was created.
        updated_at (DateTimeField): The timestamp when the company was last updated.
    """

    edinet_code = models.CharField(
        verbose_name="ＥＤＩＮＥＴコード", max_length=6, null=True
    )
    type_of_submitter = models.CharField(
        verbose_name="提出者種別", max_length=30, null=True
    )
    listing_status = models.CharField(verbose_name="上場区分", max_length=3, null=True)
    consolidated_status = models.CharField(
        verbose_name="連結の有無", max_length=1, null=True
    )
    capital = models.IntegerField(verbose_name="資本金", null=True)
    end_fiscal_year = models.CharField(verbose_name="決算日", max_length=6, null=True)
    submitter_name = models.CharField(
        verbose_name="提出者名", max_length=100, null=True
    )
    submitter_name_en = models.CharField(
        verbose_name="提出者名（英字）", max_length=100, null=True
    )
    submitter_name_kana = models.CharField(
        verbose_name="提出者名（ヨミ）", max_length=100, null=True
    )
    address = models.CharField(verbose_name="所在地", max_length=255, null=True)
    submitter_industry = models.CharField(
        verbose_name="提出者業種", max_length=25, null=True
    )
    securities_code = models.CharField(
        verbose_name="証券コード", max_length=5, null=True
    )
    corporate_number = models.CharField(
        verbose_name="提出者法人番号", max_length=13, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Counting(models.Model):
    """
    計数データ

    Attributes:
        company (ForeignKey): A foreign key to the associated Company object.
        period_start (DateField): The starting date of the period for which the data represents.
        period_end (DateField): The ending date of the period for which the data represents.
        submit_date (DateField): The date and time when the data was submitted.
        avg_salary (IntegerField): The average annual salary of the company's employees in Japanese yen.
        avg_tenure (FloatField): The average length of employment in years.
        avg_age (FloatField): The average age of the employees in years.
        number_of_employees (IntegerField): The total number of employees in the company.
        created_at (DateTimeField): The date and time when the object was created.
        updated_at (DateTimeField): The date and time when the object was last updated.
    """

    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)
    period_start = models.DateField(verbose_name="期間（自）", null=True)
    period_end = models.DateField(verbose_name="期間（至）", null=True)
    submit_date = models.DateField(verbose_name="提出日時")
    avg_salary = models.IntegerField(verbose_name="平均年間給与（円）", null=True)
    avg_tenure = models.FloatField(verbose_name="平均勤続年数（年）", null=True)
    avg_age = models.FloatField(verbose_name="平均年齢（歳）", null=True)
    number_of_employees = models.IntegerField(verbose_name="従業員数（人）", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["company", "submit_date"]
