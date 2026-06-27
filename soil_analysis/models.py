from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.db import models

from lib.geo.valueobject.coord import GoogleMapsCoord


class JmaArea(models.Model):
    """
    気象庁のエリア情報を保持します。
    生データでは center という名前で取り扱われています。

    Attributes:
        code (str): エリアコード
        name (str): エリア名
    """

    code = models.CharField("エリアコード", unique=True, max_length=6)
    name = models.CharField("エリア名", max_length=100)


class JmaPrefecture(models.Model):
    """
    気象庁の都道府県情報を保持します。
    生データでは office という名前で取り扱われています。

    Attributes:
        code (str): 都道府県コード
        jma_area (JmaArea): JMAエリア
        name (str): 都道府県名
    """

    code = models.CharField("都道府県コード", unique=True, max_length=6)
    jma_area = models.ForeignKey(
        JmaArea, on_delete=models.CASCADE, verbose_name="JMAエリア"
    )
    name = models.CharField("都道府県名", max_length=100)

    def __str__(self):
        return self.name


class JmaRegion(models.Model):
    """
    気象庁のリージョン情報を保持します。
    生データでは class10 という名前で取り扱われています。

    Attributes:
        code (str): リージョンコード
        jma_prefecture (JmaPrefecture): 都道府県
        name (str): リージョン名
    """

    code = models.CharField("リージョンコード", unique=True, max_length=6)
    jma_prefecture = models.ForeignKey(
        JmaPrefecture, on_delete=models.CASCADE, verbose_name="都道府県"
    )
    name = models.CharField("リージョン名", max_length=100)


class JmaCity(models.Model):
    """
    気象庁の市区町村情報を保持します。
    生データでは class20 という名前で取り扱われています。

    Attributes:
        code (str): 市区町村コード
        jma_region (JmaRegion): リージョン
        name (str): 市区町村名
    """

    code = models.CharField("市区町村コード", unique=True, max_length=7)
    jma_region = models.ForeignKey(
        JmaRegion, on_delete=models.CASCADE, verbose_name="リージョン"
    )
    name = models.CharField("市区町村名", max_length=100)

    def __str__(self):
        return self.name


class JmaAmedas(models.Model):
    """
    気象庁のアメダス観測所情報を保持します。

    Attributes:
        code (str): アメダス観測所コード
        jma_region (JmaRegion): リージョン
    """

    code = models.CharField("アメダス観測所コード", unique=True, max_length=5)
    jma_region = models.ForeignKey(
        JmaRegion, on_delete=models.CASCADE, verbose_name="リージョン"
    )


class JmaWeatherCode(models.Model):
    """
    天気コードマスタ。

    Attributes:
        code (str): 天気コード
        summary_code (str): 集計用コード
        image (str): 画像ファイル名
        name (str): 天気名（日本語）
        name_en (str): 天気名（英語）
    """

    code = models.CharField("天気コード", unique=True, max_length=3)
    summary_code = models.CharField("集計用コード", max_length=3)
    image = models.CharField("画像ファイル名", max_length=7)
    name = models.CharField("天気名（日本語）", max_length=20)
    name_en = models.CharField("天気名（英語）", max_length=100)


class JmaWeather(models.Model):
    """
    日々の天気情報を保持します。

    See Also: https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=2820100

    Attributes:
        jma_region (JmaRegion): リージョン
        reporting_date (date): 報告日
        jma_weather_code (JmaWeatherCode): 天気コード
        weather_text (str): 天気概況
        wind_text (str): 風の概況
        wave_text (str): 波の概況
        avg_rain_probability (float): 降水確率
        avg_min_temperature (float): 最低気温
        avg_max_temperature (float): 最高気温
        avg_max_wind_speed (float): 最大風速
    """

    jma_region = models.ForeignKey(
        JmaRegion, on_delete=models.CASCADE, verbose_name="リージョン"
    )
    reporting_date = models.DateField("報告日")
    jma_weather_code = models.ForeignKey(
        JmaWeatherCode, on_delete=models.CASCADE, verbose_name="天気コード"
    )
    weather_text = models.CharField("天気概況", max_length=255)
    wind_text = models.CharField("風の概況", max_length=255)
    wave_text = models.CharField("波の概況", max_length=255)
    avg_rain_probability = models.FloatField("降水確率", null=True)
    avg_min_temperature = models.FloatField("最低気温", null=True)
    avg_max_temperature = models.FloatField("最高気温", null=True)
    avg_max_wind_speed = models.FloatField("最大風速", null=True)

    class Meta:
        unique_together = (("jma_region", "reporting_date"),)


class JmaWarning(models.Model):
    """
    気象警報・注意報情報を保持します。

    See Also: https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code=2810000&lang=ja

    Attributes:
        jma_region (JmaRegion): リージョン
        warnings (str): 警報・注意報内容
    """

    jma_region = models.ForeignKey(
        JmaRegion, on_delete=models.CASCADE, verbose_name="リージョン"
    )
    warnings = models.CharField("警報・注意報内容", max_length=100)

    class Meta:
        unique_together = ("jma_region",)


class UserAttribute(models.Model):
    """
    土壌分析アプリ特有のユーザー属性。

    - Django 標準の auth.User と 1:1 で紐づく（認証や氏名・メール等は auth.User を参照）
    - 土壌分析ドメイン固有の情報を保持

    Attributes:
        user (OneToOneField): ユーザ
        role (CharField): ロール (OWNER/STAFF)
        address (TextField): 住所
        organization (CharField): 所属
        area (CharField): 担当エリア
        remark (TextField): 備考
        created_at (DateTimeField): 作成日時
        updated_at (DateTimeField): 更新日時
    """

    class Role(models.TextChoices):
        """
        ロール定義。

        Attributes:
            OWNER: 圃場オーナー
            STAFF: 採土スタッフ
        """

        OWNER = "owner", "圃場オーナー"
        STAFF = "staff", "採土スタッフ"

    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="soil_profile",
        verbose_name="ユーザ",
    )
    role = models.CharField(
        "ロール",
        max_length=20,
        choices=Role,
    )
    address = models.TextField("住所", null=True, blank=True)
    organization = models.CharField("所属", max_length=255, null=True, blank=True)
    area = models.CharField("担当エリア", max_length=255, null=True, blank=True)
    remark = models.TextField("備考", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class CompanyCategory(models.Model):
    """
    顧客カテゴリマスタ。

    Attributes:
        name (str): 名称
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("名称", max_length=256)
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    """
    顧客マスタ。

    Attributes:
        name (str): 名称
        image (ImageField): 画像
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
        category (CompanyCategory): カテゴリ
    """

    name = models.CharField("名称", max_length=256)
    image = models.ImageField("画像", upload_to="company/", null=True, blank=True)
    remark = models.TextField("備考", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    category = models.ForeignKey(
        CompanyCategory, on_delete=models.CASCADE, verbose_name="カテゴリ"
    )


class Crop(models.Model):
    """
    作物マスタ。

    Attributes:
        name (str): 作物名
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("作物名", max_length=256)
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class LandBlock(models.Model):
    """
    圃場ブロックマスタ。

    圃場は3x3の9ブロックに分かれる。
    計測器（土壌硬度計測器など）の仕様および配置関係は以下の通り：

    ┌────┬────┬────┐
    │ C3 │ B3 │ A3 │  (Row 3)
    ├────┼────┼────┤
    │ C2 │ B2 │ A2 │  (Row 2)
    ├────┼────┼────┤
    │ C1 │ B1 │ A1 │  (Row 1)
    └────┴────┴────┘
     (Col C) (Col B) (Col A)

    - 行（Row）: 1, 2, 3
    - 列 (Col) : A, B, C
    - 実際の計測シナリオでは、5ブロック（C1, C3, B2, A1, A3）のみを計測する場合がある。

    Attributes:
        name (str): ブロック名
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("ブロック名", max_length=256)
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="name_unique"),
        ]


class LandPeriod(models.Model):
    """
    時期マスタ。

    Attributes:
        year (int): 西暦年
        name (str): 時期の名前
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    year = models.IntegerField("西暦年")
    name = models.CharField("時期の名前", max_length=256)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["year", "name"], name="year_name_unique"),
        ]


class CultivationType(models.Model):
    """
    作型マスタ。

    Attributes:
        name (str): 作型の名前
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("作型の名前", max_length=256)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self):
        return self.name


class Land(models.Model):
    """
    圃場マスタ。

    Attributes:
        name (str): 圃場名
        jma_city (JmaCity): 市区町村 (気象庁分類)
        center (str): 中心座標
        area (float): 面積
        image (File): 画像
        remark (str): 備考
        company (Company): 所属法人
        cultivation_type (CultivationType): 作型
        owner (User): オーナー
    """

    name = models.CharField("圃場名", max_length=256)
    jma_city = models.ForeignKey(
        JmaCity, on_delete=models.CASCADE, verbose_name="市区町村(気象庁分類)"
    )
    center = models.CharField("中心座標", max_length=256)
    area = models.FloatField("面積", null=True, blank=True)
    image = models.ImageField("画像", upload_to="land/", null=True, blank=True)
    remark = models.TextField("備考", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, verbose_name="所属法人"
    )
    cultivation_type = models.ForeignKey(
        CultivationType, on_delete=models.CASCADE, verbose_name="作型"
    )
    owner = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, verbose_name="オーナー"
    )

    def to_google(self) -> GoogleMapsCoord:
        """
        圃場の中心座標をGoogleMapsCoord形式で返します

        Returns:
            GoogleMapsCoord: 圃場の中心座標
        """
        lat_str, lng_str = self.center.split(",")
        latitude = float(lat_str.strip())
        longitude = float(lng_str.strip())
        return GoogleMapsCoord(latitude=latitude, longitude=longitude)


class SamplingMethod(models.Model):
    """
    採土法マスタ。

    Attributes:
        name (str): 採土法名
        times (int): 採土回数
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("採土法名", max_length=256)
    times = models.IntegerField("採土回数")
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class LandLedger(models.Model):
    """
    圃場における特定の時期（LandPeriod）の作業・分析を管理する台帳。

    Attributes:
        sampling_date (date): 採土日
        analysis_request_date (date): 分析依頼日
        reporting_date (date): 報告日
        analytical_agency (Company): 分析機関
        crop (Crop): 作物
        land (Land): 圃場
        land_period (LandPeriod): 時期
        sampling_method (SamplingMethod): 採土法
        sampling_staff (User): 採土スタッフ
        hardness_image (ImageField): 硬度分布図
    """

    sampling_date = models.DateField("採土日")
    analysis_request_date = models.DateField("分析依頼日", null=True)
    reporting_date = models.DateField("報告日", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    analytical_agency = models.ForeignKey(
        Company, on_delete=models.CASCADE, verbose_name="分析機関"
    )
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE, verbose_name="作物")
    land = models.ForeignKey(Land, on_delete=models.CASCADE, verbose_name="圃場")
    land_period = models.ForeignKey(
        LandPeriod, on_delete=models.CASCADE, verbose_name="時期"
    )
    sampling_method = models.ForeignKey(
        SamplingMethod, on_delete=models.CASCADE, verbose_name="採土法"
    )
    sampling_staff = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, verbose_name="採土スタッフ"
    )
    hardness_image = models.ImageField(
        "硬度分布図", upload_to="hardness_images", null=True, blank=True
    )

    @property
    def analysis_number(self) -> int | None:
        measurement = getattr(self, "soil_chemical_measurement", None)
        return measurement.analysis_number if measurement else None

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["land", "land_period"], name="land_period_unique"
            ),
        ]

    def __str__(self):
        return f"{self.land.company.name} - {self.land.name} ({self.land_period.year} {self.land_period.name})"


class SamplingOrder(models.Model):
    """
    採土法の採土順。

    Attributes:
        ordering (int): 順序
        remark (str): 備考
        land_block (LandBlock): 圃場ブロック
        sampling_method (SamplingMethod): 採土法
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    ordering = models.IntegerField("順序")
    remark = models.TextField("備考", null=True)
    land_block = models.ForeignKey(
        LandBlock, on_delete=models.CASCADE, verbose_name="圃場ブロック"
    )
    sampling_method = models.ForeignKey(
        SamplingMethod, on_delete=models.CASCADE, verbose_name="採土法"
    )
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class SoilChemicalMeasurement(models.Model):
    """
    圃場単位での化学分析結果を保存します。

    Attributes:
        analysis_number (int): 分析番号
        ec (FloatField): 電気伝導率
        nh4n (FloatField): アンモニア態窒素
        no3n (FloatField): 硝酸態窒素
        ph (FloatField): 水素イオン濃度
        cao (FloatField): 交換性石灰
        mgo (FloatField): 交換性苦土
        k2o (FloatField): 交換性加里
        lime_saturation (FloatField): 石灰飽和度
        magnesia_saturation (FloatField): 苦土飽和度
        potash_saturation (FloatField): 加里飽和度
        base_saturation (FloatField): 塩基飽和度
        phosphorus_absorption (FloatField): リン酸吸収係数
        p2o5 (FloatField): 可給態リン酸
        cec (FloatField): 塩基置換容量
        humus (FloatField): 腐植
        bulk_density (FloatField): 仮比重
        source_file (str): データ元ファイル
        land_ledger (LandLedger): 台帳
    """

    analysis_number = models.IntegerField("分析番号", null=True, unique=True)
    ec = models.FloatField("電気伝導率", null=True)
    nh4n = models.FloatField("アンモニア態窒素", null=True)
    no3n = models.FloatField("硝酸態窒素", null=True)
    ph = models.FloatField("水素イオン濃度", null=True)
    cao = models.FloatField("交換性石灰", null=True)
    mgo = models.FloatField("交換性苦土", null=True)
    k2o = models.FloatField("交換性加里", null=True)
    lime_saturation = models.FloatField("石灰飽和度", null=True)
    magnesia_saturation = models.FloatField("苦土飽和度", null=True)
    potash_saturation = models.FloatField("加里飽和度", null=True)
    base_saturation = models.FloatField("塩基飽和度", null=True)
    phosphorus_absorption = models.FloatField("リン酸吸収係数", null=True)
    p2o5 = models.FloatField("可給態リン酸", null=True)
    cec = models.FloatField("塩基置換容量", null=True)
    humus = models.FloatField("腐植", null=True)
    bulk_density = models.FloatField("仮比重", null=True)

    @property
    def total_nitrogen(self) -> float | None:
        if self.nh4n is None or self.no3n is None:
            return None
        return self.nh4n + self.no3n

    @property
    def nh4_per_nitrogen(self) -> float | None:
        total = self.total_nitrogen
        if not total:
            return None
        return (self.nh4n / total) * 100

    @property
    def cao_per_mgo(self) -> float | None:
        if self.cao is None or self.mgo is None or self.mgo == 0:
            return None
        return self.cao / self.mgo

    @property
    def mgo_per_k2o(self) -> float | None:
        if self.mgo is None or self.k2o is None or self.k2o == 0:
            return None
        return self.mgo / self.k2o

    source_file = models.CharField("データ元ファイル", max_length=256, null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    land_ledger = models.OneToOneField(
        LandLedger,
        on_delete=models.CASCADE,
        verbose_name="台帳",
        related_name="soil_chemical_measurement",
    )


class SoilChemicalMeasurementImportErrors(models.Model):
    """
    化学分析取り込み時のエラーリスト。

    Attributes:
        row_number (int): 行番号
        land_name (str): 圃場名
        message (str): エラーメッセージ
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    row_number = models.IntegerField("行番号", null=True)
    land_name = models.CharField("圃場名", max_length=256, null=True)
    message = models.TextField("エラーメッセージ")
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class LandReview(models.Model):
    """
    台帳（圃場×時期）に対する評価コメント。

    Attributes:
        comment (str): コメント
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
        land_ledger (LandLedger): 台帳
    """

    comment = models.TextField("コメント")
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    land_ledger = models.ForeignKey(
        LandLedger, on_delete=models.CASCADE, verbose_name="台帳"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["land_ledger"], name="land_ledger_unique"),
        ]


class Device(models.Model):
    """
    土壌硬度計マスタ。

    Attributes:
        name (str): デバイス名
        max_memory (int): 最大メモリ数
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("デバイス名", max_length=256)
    max_memory = models.IntegerField("最大メモリ数", null=True, blank=True)
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class SoilHardnessMeasurement(models.Model):
    """
    土壌硬度CSVから取り込んだ深度別の測定レコード。

    CSV取り込み直後は未関連付けで、後続の関連付け画面で台帳・圃場ブロックを確定する。
    1回の貫入計測は同一の set_device, set_memory, set_datetime を持つ複数 depth レコードで構成される。
    folder はアップロードZIP内の親フォルダ名で、関連付け前の圃場グルーピングに使う。

    Attributes:
        set_memory (int): メモリ番号
        set_datetime (datetime): 測定日時
        set_depth (int): 設定深度
        set_spring (int): スプリング番号
        set_cone (int): コーン番号
        depth (int): 深度(cm)
        pressure (int): 圧力(kPa)
        folder (str): アップロードZIP内の親フォルダ名。関連付け画面で圃場グループを識別するために使う。
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
        set_device (Device): 測定デバイス。set_memory, set_datetime, depth と組み合わせて一意性を判定する。
        land_block (LandBlock | None): 関連付け後の圃場ブロック。CSV取り込み直後は未設定。
        land_ledger (LandLedger | None): 関連付け後の台帳。CSV取り込み直後は未設定。
    """

    set_memory = models.IntegerField("メモリ番号")
    set_datetime = models.DateTimeField("測定日時")
    set_depth = models.IntegerField("設定深度")
    set_spring = models.IntegerField("スプリング番号")
    set_cone = models.IntegerField("コーン番号")
    depth = models.IntegerField("深度(cm)")
    pressure = models.IntegerField("圧力(kPa)")
    folder = models.CharField("フォルダ名", max_length=256)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)
    set_device = models.ForeignKey(
        Device, on_delete=models.CASCADE, verbose_name="測定デバイス"
    )
    land_block = models.ForeignKey(
        LandBlock, null=True, on_delete=models.CASCADE, verbose_name="圃場ブロック"
    )
    land_ledger = models.ForeignKey(
        LandLedger, null=True, on_delete=models.CASCADE, verbose_name="台帳"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["set_device", "set_memory", "set_datetime", "depth"],
                name="device_memory_datetime_depth_unique",
            ),
        ]


class SoilHardnessMeasurementImportErrors(models.Model):
    """
    土壌硬度測定 生データ 取り込みエラーリスト。

    Attributes:
        file (str): ファイル名
        folder (str): フォルダ名
        message (str): エラーメッセージ
        remark (str): 備考
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    file = models.CharField("ファイル名", max_length=256)
    folder = models.CharField("フォルダ名", max_length=256)
    message = models.TextField("エラーメッセージ")
    remark = models.TextField("備考", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class RouteSuggestImport(models.Model):
    """
    KMLの圃場座標リストをいったん保存するテーブル。

    Attributes:
        name (str): 名称
        coord (str): 座標文字列
        ordering (int): 順序
        created_at (datetime): 作成日時
        updated_at (datetime): 更新日時
    """

    name = models.CharField("名称", max_length=256)
    coord = models.CharField("座標文字列", max_length=256)
    ordering = models.IntegerField("順序", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)


class RokunoheLandRegistry(models.Model):
    """
    六戸の登記簿固定データ。
    CSVの日本語列を英語フィールドとして保持する。

    Attributes:
        ledger_type (str): 帳簿種別
        address (str): 住所
        coordinate (str): 座標
        registered_land_category (str): 登記地目
        current_land_category (str): 現況地目
        registered_area (int): 登記面積(㎡)
        current_area (int): 現況面積(㎡)
        remarks (str): 備考
    """

    ledger_type = models.CharField("帳簿種別", max_length=100)
    address = models.CharField("住所", max_length=255)
    coordinate = models.CharField("座標", max_length=100)
    registered_land_category = models.CharField("登記地目", max_length=50)
    current_land_category = models.CharField("現況地目", max_length=50)
    registered_area = models.PositiveIntegerField("登記面積(㎡)")
    current_area = models.PositiveIntegerField("現況面積(㎡)")
    remarks = models.TextField("備考", blank=True, default="")

    class Meta:
        db_table = "rokunohe_land_registry"
        verbose_name = "六戸登記簿"
        verbose_name_plural = "六戸登記簿"

    def __str__(self):
        return f"{self.address} ({self.coordinate})"

    def google_maps_url(self) -> str:
        return f"https://www.google.com/maps?q={quote(self.coordinate)}"


class AgriculturalRegion(models.Model):
    """
    e-Stat の農業統計を集計する対象地域です。

    Attributes:
        area_code: e-Stat の地域エリア単一コード。
        name: 地域名。
        prefecture_name: 都道府県名。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    area_code = models.CharField("地域コード", max_length=10, unique=True)
    name = models.CharField("地域名", max_length=100)
    prefecture_name = models.CharField("都道府県名", max_length=100)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self):
        return f"{self.prefecture_name}{self.name} ({self.area_code})"


class EstatDataset(models.Model):
    """
    e-Stat から継続取得する統計表と指標定義です。

    `filters` には `cdCat01` や `cdTab` など、e-Stat API にそのまま渡す
    絞り込みパラメータを保持します。地域コードは取得時に対象地域から補います。

    Attributes:
        indicator_key: レポート計算で使う指標キー。
        display_name: 画面に表示する指標名。
        stats_data_id: e-Stat 統計表表示 ID。
        filters: e-Stat API に渡す絞り込み条件。
        unit: 値の単位。
        category: 指標カテゴリ。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    indicator_key = models.CharField("指標キー", max_length=100, unique=True)
    display_name = models.CharField("表示名", max_length=255)
    stats_data_id = models.CharField("統計表ID", max_length=30)
    filters = models.JSONField("e-Statフィルタ", default=dict, blank=True)
    unit = models.CharField("単位", max_length=50, blank=True, default="")
    category = models.CharField("カテゴリ", max_length=100, blank=True, default="")
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    def __str__(self):
        return self.display_name


class AgriculturalStatisticSnapshot(models.Model):
    """
    e-Stat から取得した農業統計値の履歴です。

    同じ地域・指標・期間でも、e-Stat 側の値やメタデータが変わった場合は
    `source_hash` が変わり、新しいスナップショットとして保存します。

    Attributes:
        region: 対象地域。
        dataset: 指標定義。
        period_label: 統計値の対象期間。
        value: 統計値。
        fetched_at: 取得日時。
        estat_updated_at: e-Stat 側の公開・更新日時。
        raw_data: e-Stat の値レコード。
        source_hash: 取得値とメタデータから作る重複判定用ハッシュ。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    region = models.ForeignKey(
        AgriculturalRegion, on_delete=models.CASCADE, verbose_name="対象地域"
    )
    dataset = models.ForeignKey(
        EstatDataset, on_delete=models.CASCADE, verbose_name="指標定義"
    )
    period_label = models.CharField("対象期間", max_length=50)
    value = models.FloatField("値", null=True, blank=True)
    fetched_at = models.DateTimeField("取得日時")
    estat_updated_at = models.DateTimeField("e-Stat更新日時", null=True, blank=True)
    raw_data = models.JSONField("e-Stat raw data", default=dict, blank=True)
    source_hash = models.CharField("ソースハッシュ", max_length=64)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["region", "dataset", "period_label", "source_hash"],
                name="agri_snapshot_region_dataset_period_hash_unique",
            )
        ]
        ordering = ["-fetched_at", "dataset__indicator_key"]


class AgriculturalRiskReport(models.Model):
    """
    地域別の離農・管理不能農地リスク集計結果です。

    Attributes:
        region: 対象地域。
        report_date: 集計日。
        total_cultivated_area: 現在の経営耕地面積。
        age_70_plus_area: 70歳以上の経営体が保有する面積。
        age_60s_area: 60代の経営体が保有する面積。
        no_successor_ratio: 後継者なし割合。
        shrink_stop_intention_ratio: 縮小・中止意向の割合。
        supplemental_unmanageable_area: 補助指標による管理不能化候補面積。
        aging_risk: 高齢化リスク。
        succession_risk: 継承リスク。
        intention_risk: 意向リスク。
        retirement_confirmed_area: 離農確定候補面積。
        retirement_reserve_area: 離農予備軍面積。
        unmanageable_candidate_area: 管理不能化候補面積。
        farmland_maintenance_rate: 10年後の農地維持率。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    region = models.ForeignKey(
        AgriculturalRegion, on_delete=models.CASCADE, verbose_name="対象地域"
    )
    report_date = models.DateField("集計日")
    total_cultivated_area = models.FloatField("現在の経営耕地面積", null=True)
    age_70_plus_area = models.FloatField("70歳以上面積", null=True)
    age_60s_area = models.FloatField("60代面積", null=True)
    no_successor_ratio = models.FloatField("後継者なし割合", null=True)
    shrink_stop_intention_ratio = models.FloatField("縮小・中止意向割合", null=True)
    supplemental_unmanageable_area = models.FloatField("補助管理不能面積", default=0)
    aging_risk = models.FloatField("高齢化リスク", null=True)
    succession_risk = models.FloatField("継承リスク", null=True)
    intention_risk = models.FloatField("意向リスク", null=True)
    retirement_confirmed_area = models.FloatField("離農確定候補面積", null=True)
    retirement_reserve_area = models.FloatField("離農予備軍面積", null=True)
    unmanageable_candidate_area = models.FloatField("管理不能化候補面積", null=True)
    farmland_maintenance_rate = models.FloatField("10年後農地維持率", null=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["region", "report_date"],
                name="agri_risk_report_region_date_unique",
            )
        ]
        ordering = ["-report_date", "-id"]


class SupplementalRiskIndicator(models.Model):
    """
    e-Stat 以外の公開情報から補助的に扱うリスク指標です。

    六戸町に限定できない全国統計も、地域粒度を明示したうえで保存します。

    Attributes:
        indicator_key: 指標キー。
        display_name: 画面表示名。
        source_name: 取得元名。
        source_url: 取得元URL。
        region_label: 全国、青森県などの地域粒度。
        period_label: 統計値の時点。
        value: 統計値。
        unit: 単位。
        category: 指標カテゴリ。
        note: 指標の読み方や注意点。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    indicator_key = models.CharField("指標キー", max_length=100, unique=True)
    display_name = models.CharField("表示名", max_length=255)
    source_name = models.CharField("取得元", max_length=255)
    source_url = models.URLField("取得元URL")
    region_label = models.CharField("地域粒度", max_length=100)
    period_label = models.CharField("対象期間", max_length=100)
    value = models.FloatField("値", null=True, blank=True)
    unit = models.CharField("単位", max_length=50, blank=True, default="")
    category = models.CharField("カテゴリ", max_length=100, blank=True, default="")
    note = models.TextField("備考", blank=True, default="")
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        ordering = ["category", "indicator_key"]

    def __str__(self):
        return self.display_name
