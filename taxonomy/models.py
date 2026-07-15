import re
from urllib.parse import urlencode

from django.conf import settings
from django.db import models


class JmaWeatherCode(models.Model):
    """
    天気コードマスタ（taxonomy にローカライズ）

    Attributes:
        code (CharField): "123"
        summary_code (CharField): "100"
        image (CharField): "100.svg"
        name (CharField): "晴"
        name_en (CharField): "CLEAR, FREQUENT SNOW FLURRIES LATER"
    """

    code = models.CharField(unique=True, max_length=3)
    summary_code = models.CharField(max_length=3)
    image = models.CharField(max_length=7)
    name = models.CharField(max_length=20)
    name_en = models.CharField(max_length=100)


class Kingdom(models.Model):
    """
    界マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Phylum(models.Model):
    """
    門マスタ フィラムと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Classification(models.Model):
    """
    綱マスタ コウと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    phylum = models.ForeignKey(Phylum, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Family(models.Model):
    """
    科マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    classification = models.ForeignKey(Classification, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Genus(models.Model):
    """
    属マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Species(models.Model):
    """
    種マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    genus = models.ForeignKey(Genus, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class NaturalMonument(models.Model):
    """
    天然記念物区分
    """

    name = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Tag(models.Model):
    """
    タグマスタ
    """

    name = models.CharField(max_length=20)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Breed(models.Model):
    """
    品種。

    Attributes:
        name: 品種・系統・分類対象名。
        name_kana: よみがな。
        image: 画像。
        remark: メモ。
        natural_monument: 天然記念物区分。
        species: 種。
    """

    name = models.CharField("品種・系統・分類対象名", max_length=255)
    name_kana = models.CharField("よみがな", max_length=255)
    image = models.ImageField("画像", upload_to="taxonomy/breed", blank=True)
    remark = models.CharField("メモ", max_length=255, null=True, blank=True)
    natural_monument = models.ForeignKey(
        NaturalMonument,
        verbose_name="天然記念物区分",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    species = models.ForeignKey(Species, verbose_name="種", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="breed_name_unique")
        ]

    @classmethod
    def form_field(cls, field_name, **kwargs):
        return cls._meta.get_field(field_name).formfield(**kwargs)


class BreedTags(models.Model):
    """
    品種のタグ
    """

    breed = models.ForeignKey(Breed, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["breed", "tag"], name="breed_tag_unique")
        ]


class LLMTaxonomyCandidate(models.Model):
    """
    LLMが生成した未確認の分類候補。

    ユーザーがレビューする前の候補を確認済みtaxonomyデータと分けて保持し、
    承認された候補だけをBreedと分類階層へ反映する。

    Attributes:
        status: レビュー状態。
        kingdom_name: 界の名前。
        kingdom_name_en: 界の英名。
        phylum_name: 門の名前。
        phylum_name_en: 門の英名。
        classification_name: 綱の名前。
        classification_name_en: 綱の英名。
        family_name: 科の名前。
        family_name_en: 科の英名。
        genus_name: 属の名前。
        genus_name_en: 属の英名。
        species_name: 種の名前。
        species_name_en: 種の英名。
        breed_name: 品種・系統・分類対象名。
        breed_name_kana: 品種・系統・分類対象名のよみがな。
        source_name: 確認に使う出典名。
        source_url: 確認に使う出典URL。
        external_taxon_id: 外部taxonomyデータベース上のID。
        llm_note: LLM生成時の補足や元出力。
        approved_breed: 承認後に作成された品種。
        reviewed_by: 承認または却下したユーザー。
        reviewed_at: 承認または却下した日時。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    class ReviewStatus(models.TextChoices):
        """
        LLM分類候補のレビュー状態。

        Attributes:
            PENDING: 未レビューの候補。
            APPROVED: 確認済みデータへ登録された候補。
            REJECTED: 確認済みデータへ登録しない候補。
        """

        PENDING = "pending", "レビュー待ち"
        APPROVED = "approved", "承認済み"
        REJECTED = "rejected", "却下"

    status = models.CharField(
        "レビュー状態",
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    kingdom_name = models.CharField("界の名前", max_length=255)
    kingdom_name_en = models.CharField("界の英名", max_length=255, blank=True)
    phylum_name = models.CharField("門の名前", max_length=255)
    phylum_name_en = models.CharField("門の英名", max_length=255, blank=True)
    classification_name = models.CharField("綱の名前", max_length=255)
    classification_name_en = models.CharField("綱の英名", max_length=255, blank=True)
    family_name = models.CharField("科の名前", max_length=255)
    family_name_en = models.CharField("科の英名", max_length=255, blank=True)
    genus_name = models.CharField("属の名前", max_length=255)
    genus_name_en = models.CharField("属の英名", max_length=255, blank=True)
    species_name = models.CharField("種の名前", max_length=255)
    species_name_en = models.CharField("種の英名", max_length=255, blank=True)
    breed_name = models.CharField("品種・系統・分類対象名", max_length=255)
    breed_name_kana = models.CharField(
        "品種・系統・分類対象名のよみがな", max_length=255, blank=True
    )
    source_name = models.CharField("出典名", max_length=255, blank=True)
    source_url = models.URLField("出典URL", max_length=500, blank=True)
    external_taxon_id = models.CharField("外部taxonomy ID", max_length=255, blank=True)
    llm_note = models.TextField("LLM生成メモ", blank=True)
    approved_breed = models.ForeignKey(
        Breed,
        verbose_name="承認後の品種",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="レビュー担当者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField("レビュー日時", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"{self.breed_name} ({self.get_status_display()})"

    @property
    def gbif_taxon_search_url(self) -> str:
        query = self._gbif_taxon_search_query()
        query_params = urlencode({"q": query})
        return f"https://www.gbif.org/taxon/search?{query_params}"

    def _gbif_taxon_search_query(self) -> str:
        for candidate_name in [self.species_name, self.species_name_en]:
            if self._looks_like_scientific_name(candidate_name):
                return candidate_name
        return self.species_name

    @staticmethod
    def _looks_like_scientific_name(name: str) -> bool:
        return re.match(r"^[A-Z][a-z]+ [a-z][a-z-]+$", name) is not None


class LLMTaxonomyCandidateGenerationJob(models.Model):
    """
    LLM分類候補生成の進捗を保持するジョブ。

    生成対象名のリスト作成と、対象ごとの詳細生成を別ステップとして保存し、
    画面ポーリングで現在の対象名、成功件数、失敗件数を表示できるようにする。

    Attributes:
        status: ジョブの実行状態。
        current_step: 現在実行中の処理名。
        current_target: 現在生成中または最後に処理した対象名。
        target_names: 今回詳細生成する対象名の一覧。
        candidate_ids: 保存できたLLM分類候補IDの一覧。
        failures: 生成または保存に失敗した対象名と理由の一覧。
        is_processing: いずれかのリクエストが現在1ステップを実行中かどうか。
        processing_started_at: 現在の1ステップ実行を開始した日時。
        processing_by: 現在の1ステップ実行を開始したユーザー。
        processing_token: 現在の1ステップ実行を開始したブラウザタブの識別子。
        total_count: 詳細生成対象の総数。
        processed_count: 詳細生成を試行した対象数。
        success_count: 保存できた候補数。
        failed_count: 詳細生成または保存に失敗した対象数。
        error_message: ジョブ全体を続行できないエラー。
        created_by: ジョブを開始したユーザー。
        started_at: ジョブ開始日時。
        finished_at: ジョブ終了日時。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    class JobStatus(models.TextChoices):
        """
        LLM分類候補生成ジョブの実行状態。

        Attributes:
            PENDING: 対象リスト作成前の状態。
            RUNNING: 対象リスト作成後、詳細生成を進めている状態。
            COMPLETED: 対象を最後まで処理した状態。
            FAILED: 対象リスト作成などでジョブ全体が失敗した状態。
        """

        PENDING = "pending", "準備中"
        RUNNING = "running", "生成中"
        COMPLETED = "completed", "完了"
        FAILED = "failed", "失敗"

    status = models.CharField(
        "ジョブ状態",
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING,
    )
    current_step = models.CharField("現在ステップ", max_length=100, blank=True)
    current_target = models.CharField("現在の生成対象", max_length=255, blank=True)
    target_names = models.JSONField("生成対象名一覧", default=list, blank=True)
    candidate_ids = models.JSONField("保存済み候補ID一覧", default=list, blank=True)
    failures = models.JSONField("失敗対象一覧", default=list, blank=True)
    is_processing = models.BooleanField("処理中", default=False)
    processing_started_at = models.DateTimeField("処理開始日時", null=True, blank=True)
    processing_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="処理実行者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processing_llm_taxonomy_generation_jobs",
    )
    processing_token = models.CharField("処理タブ識別子", max_length=100, blank=True)
    total_count = models.PositiveSmallIntegerField("生成対象総数", default=0)
    processed_count = models.PositiveSmallIntegerField("処理済み対象数", default=0)
    success_count = models.PositiveSmallIntegerField("成功件数", default=0)
    failed_count = models.PositiveSmallIntegerField("失敗件数", default=0)
    error_message = models.TextField("エラーメッセージ", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="作成者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField("開始日時", null=True, blank=True)
    finished_at = models.DateTimeField("終了日時", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LLM分類候補生成ジョブ {self.pk} ({self.get_status_display()})"


class LivestockDistributionDataset(models.Model):
    """
    e-Stat畜産統計の鶏地域別飼養分布CSV。

    Attributes:
        title: 管理画面で識別するデータセット名。
        csv_file: media配下に保存する畜産統計CSV。
        source_name: 取得元名。
        source_stat_code: 政府統計コード。
        survey_year: 統計の対象年。
        retrieved_at: ローカル取得日。
        source_url: e-Statなどの公開統計表URL。
        note: 画面表示用の注意事項。
        is_active: 表示対象として有効かどうか。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    title = models.CharField("データセット名", max_length=255)
    csv_file = models.FileField(
        "畜産統計CSV", upload_to="taxonomy/livestock_distribution"
    )
    source_name = models.CharField("取得元名", max_length=255)
    source_stat_code = models.CharField("政府統計コード", max_length=20)
    survey_year = models.PositiveSmallIntegerField("対象年")
    retrieved_at = models.DateField("ローカル取得日")
    source_url = models.URLField("公開統計表URL", max_length=500)
    note = models.TextField("注意事項", blank=True)
    is_active = models.BooleanField("表示対象", default=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["-retrieved_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_stat_code", "survey_year"],
                name="livestock_distribution_source_year_unique",
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.survey_year})"


class FeedGroup(models.Model):
    """
    モデル: 飼料重量マスタ

    飼料重量とその分類名を保持するマスタデータ。
    """

    name = models.CharField(max_length=50, unique=True)
    weight = models.IntegerField(unique=True, help_text="飼料の重量 (単位: g)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} （{self.weight}g）"


class HenGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    hen_count = models.IntegerField()
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} ({self.hen_count}羽)"


class EggLedger(models.Model):
    """
    モデル: 鶏の産卵台帳 (Egg Ledger)
    """

    recorded_date = models.DateField()
    egg_count = models.IntegerField(null=True, blank=True)  # 産卵数 (単位: 個)
    avg_egg_weight = models.FloatField(null=True, blank=True)  # 平均卵重 (単位: g)
    temperature = models.FloatField(null=True, blank=True)  # 気温 (単位: °C)
    humidity = models.FloatField(null=True, blank=True)  # 湿度 (単位: %)
    rainfall = models.FloatField(null=True, blank=True)  # 降水量 (単位: mm)
    air_pressure = models.FloatField(null=True, blank=True)  # 気圧 (単位: hPa)
    comment = models.TextField(null=True, blank=True)  # 作業者のコメントなど

    weather_code = models.ForeignKey(JmaWeatherCode, on_delete=models.PROTECT)
    feed_group = models.ForeignKey(FeedGroup, on_delete=models.CASCADE)
    hen_group = models.ForeignKey(HenGroup, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def laying_rate(self):
        # egg_countやhen_groupがNoneの場合はゼロ埋めする
        egg_count = self.egg_count or 0
        hen_count = (
            self.hen_group.hen_count
            if self.hen_group and self.hen_group.hen_count
            else 0
        )

        # hen_countがゼロの時、ゼロ除算を防ぐ
        if hen_count == 0:
            return 0

        # レート計算
        return round((egg_count / hen_count) * 100, 2)

    def __str__(self):
        return (
            f"{self.recorded_date} - {self.hen_group.name}: "
            f"{self.egg_count}個, {self.laying_rate()}%"
        )
