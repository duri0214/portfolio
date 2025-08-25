from django.db import models


class Facility(models.Model):
    """
    福祉事務所マスタ
    """

    # 基本情報
    name = models.CharField("福祉事務所名", max_length=255)
    postal_code = models.CharField("郵便番号", max_length=20, null=True, blank=True)
    address = models.CharField("住所", max_length=255)
    phone = models.CharField("電話番号", max_length=20, null=True, blank=True)
    fax = models.CharField("FAX番号", max_length=20, null=True, blank=True)

    # 位置情報
    latitude = models.FloatField("緯度", null=True, blank=True)
    longitude = models.FloatField("経度", null=True, blank=True)
    coordinate_system = models.CharField("座標系", max_length=20, null=True, blank=True)

    # API取得情報
    updated_at = models.DateTimeField("最終更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "福祉事務所"
        verbose_name_plural = "福祉事務所一覧"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FacilityAvailability(models.Model):
    """
    民間福祉事務所の空き状況
    各福祉事務所は複数の月別空き状況レコードを持つ（1対多）
    """

    AVAILABILITY_CHOICES = [
        ("available", "空きあり"),
        ("limited", "残りわずか"),
        ("unavailable", "空きなし"),
    ]

    facility = models.ForeignKey(
        Facility,
        verbose_name="福祉事務所",
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    target_date = models.DateField(
        "対象年月",
        help_text="この空き状況情報が対象とする年月（月末日が保存されます）",
    )
    status = models.CharField(
        "空き状況", max_length=20, choices=AVAILABILITY_CHOICES, default="unavailable"
    )
    available_count = models.PositiveIntegerField("空き人数", default=0)
    remarks = models.TextField("備考", null=True, blank=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "空き状況"
        verbose_name_plural = "空き状況一覧"
        ordering = ["-updated_at"]
        unique_together = [
            ["facility", "target_date"]
        ]  # 同じ施設の同じ年月のデータは1つだけ

    def __str__(self):
        return f"{self.facility.name} - {self.status}"

    @property
    def month_year_display(self):
        """表示用の年月文字列を返す

        対象年月のtarget_dateフィールドから表示用の文字列を生成します。
        これによりバックデート入力された過去の年月も正しく表示できます。
        """
        if not self.target_date:
            return ""
        return self.target_date.strftime("%Y年%m月")

    @property
    def status_badge_class(self):
        """ステータスに応じたBootstrapのバッジクラスを返す

        空き状況を信号機のように直感的に表示するためのカラーコードを返します：
        - available (空きあり): 緑 (bg-success)
        - limited (残りわずか): 黄 (bg-warning)
        - unavailable (空きなし): 赤 (bg-danger)
        """
        if self.status == "available":
            return "bg-success"  # 緑
        elif self.status == "limited":
            return "bg-warning"  # 黄色
        else:  # unavailable
            return "bg-danger"  # 赤


class FacilityReview(models.Model):
    """
    利用者による福祉事務所のレビュー

    本来はGoogleマップのレビューなど外部サービスのレビュー情報を活用することが望ましいが、
    ハッカソン由来の著作権等の問題があるため、代替として障害者手帳の情報を入力させることで
    実際に福祉事務所を利用した障害を持つ子供の親からの質の高いレビューを収集する。

    手帳の種類と番号の組み合わせで一意性を確保し、重複投稿を防止する。
    福祉事務所側が利用者に対してレビュー記入を促すことで、より多くの有益な情報収集を目指す。
    """

    affiliated_facility_name = models.CharField(
        "民間事業所名", max_length=255, null=True, blank=True
    )

    RATING_CHOICES = [
        (1, "★"),
        (2, "★★"),
        (3, "★★★"),
        (4, "★★★★"),
        (5, "★★★★★"),
    ]

    CERTIFICATE_TYPES = [
        ("physical", "身体障害者手帳"),
        ("intellectual", "療育手帳"),
        ("mental", "精神障害者保健福祉手帳"),
        ("other", "その他"),
    ]

    facility = models.ForeignKey(
        Facility,
        verbose_name="福祉事務所",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer_name = models.CharField("投稿者名", max_length=100)
    certificate_type = models.CharField(
        "手帳の種類", max_length=20, choices=CERTIFICATE_TYPES
    )
    certificate_number = models.CharField("手帳番号", max_length=50)
    certificate_grade = models.CharField("等級", max_length=10, null=True, blank=True)
    rating = models.PositiveSmallIntegerField("評価", choices=RATING_CHOICES)
    comment = models.TextField("コメント")
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    is_approved = models.BooleanField("承認済み", default=False)

    class Meta:
        verbose_name = "福祉事務所レビュー"
        verbose_name_plural = "福祉事務所レビュー一覧"
        ordering = ["-created_at"]
        unique_together = [["certificate_type", "certificate_number"]]

    def __str__(self):
        return f"{self.facility.name}のレビュー - {self.reviewer_name}"
