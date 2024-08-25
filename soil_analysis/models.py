from django.contrib.auth import get_user_model
from django.db import models


class CompanyCategory(models.Model):
    """
    顧客カテゴリマスタ
    name 名称 e.g. 農業法人
    """

    name = models.CharField(max_length=256)
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name


class Company(models.Model):
    """
    顧客マスタ
    name 名称 e.g. (有)アグリファクトリー
    """

    name = models.CharField(max_length=256)
    image = models.ImageField(upload_to="company/", null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    category = models.ForeignKey(CompanyCategory, on_delete=models.CASCADE)


class Crop(models.Model):
    """
    作物マスタ
    name    作物名 e.g. キャベツ、レタスなど
    """

    name = models.CharField(max_length=256)
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class LandBlock(models.Model):
    """
    圃場ブロックマスタ
    name        エリア名    e.g. A1
    """

    name = models.CharField(max_length=256)
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name"], name="name_unique"),
        ]


class LandPeriod(models.Model):
    """
    時期マスタ
    year    西暦年      e.g. 2022
    name    時期の名前   e.g. 定植時
    """

    year = models.IntegerField()
    name = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["year", "name"], name="year_name_unique"),
        ]


class CultivationType(models.Model):
    """
    作型マスタ
    name    作型の名前   e.g. 路地、ビニールハウス
    """

    name = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return self.name


class Land(models.Model):
    """
    圃場マスタ
    name        圃場名
    prefecture  都道府県    e.g. 茨城県
    location    住所       e.g. 結城郡八千代町
    latlon      緯度経度    e.g. 36.164677272061,139.86772928159
    area        面積       e.g. 100㎡
    image       写真
    remark      備考
    company     法人[FK]
    owner       オーナー    e.g. Ａ生産者
    cultivation_type 作型  e.g. 露地、ビニールハウス
    """

    name = models.CharField(max_length=256)
    prefecture = models.CharField(max_length=256)
    location = models.CharField(max_length=256)
    latlon = models.CharField(null=True, blank=True, max_length=256)
    area = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to="land/", null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    cultivation_type = models.ForeignKey(CultivationType, on_delete=models.CASCADE)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)


class SamplingMethod(models.Model):
    """
    採土法マスタ e.g. 5点法
    本当は採土法1つに対して型（R型など）を複数登録する `SamplingMethodType` のようなものが OneToMany であるとよいが
    実質5点法の `R` で取りつづけると思うので仕様としては省略
    """

    name = models.CharField(max_length=256)
    times = models.IntegerField()
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class LandLedger(models.Model):
    """
    採土した日についてまとめる台帳
    採土日, 採土法, 採土者, 分析依頼日, 報告日, 分析機関, 分析番号
    """

    sampling_date = models.DateField()
    analysis_request_date = models.DateField(null=True)
    reporting_date = models.DateField(null=True)
    analysis_number = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    analytical_agency = models.ForeignKey(Company, on_delete=models.CASCADE)
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    land = models.ForeignKey(Land, on_delete=models.CASCADE)
    land_period = models.ForeignKey(LandPeriod, on_delete=models.CASCADE)
    sampling_method = models.ForeignKey(SamplingMethod, on_delete=models.CASCADE)
    sampling_staff = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["land", "land_period"], name="land_period_unique"
            ),
        ]


class SamplingOrder(models.Model):
    """
    採土法の採土順
    本当は採土法1つに対して型（R型など）を複数登録する `SamplingMethodType` のようなものが OneToMany であるとよいが
    実質5点法の `R` で取りつづけると思うので仕様としては省略
    """

    ordering = models.IntegerField()
    remark = models.TextField(null=True)
    land_block = models.ForeignKey(LandBlock, on_delete=models.CASCADE)
    sampling_method = models.ForeignKey(SamplingMethod, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class LandScoreChemical(models.Model):
    """
    顧客が持つ圃場をエリア単位で１レコードに収録します
    圃場ひとつは９つのエリアに分かれるが計測は5エリア✕5箇所で、1圃場あたり25箇所計測
    ec                      電気伝導率 e.g. 1(mS/cm)
    nh4n                    アンモニア態窒素 e.g. 1(mg/100g)
    no3n                    硝酸態窒素 e.g. 1(mg/100g)
    total_nitrogen          無機態窒素（NH4＋NO3）
    nh4_per_nitrogen        アンモニア態窒素比
    ph                      水素イオン濃度
    cao                     交換性石灰
    mgo                     交換性苦土
    k2o                     交換性加里
    base_saturation         塩基飽和度 e.g. 0.57
    cao_per_mgo             CaO/MgO e.g. 0.57
    mgo_per_k2o             MgO/K2O e.g. 0.57
    phosphorus_absorption   リン酸吸収係数
    p2o5                    可給態リン酸
    cec                     塩基置換容量
    humus                   腐植
    bulk_density            仮比重
    """

    ec = models.FloatField(null=True)
    nh4n = models.FloatField(null=True)
    no3n = models.FloatField(null=True)
    total_nitrogen = models.FloatField(null=True)
    nh4_per_nitrogen = models.FloatField(null=True)
    ph = models.FloatField(null=True)
    cao = models.FloatField(null=True)
    mgo = models.FloatField(null=True)
    k2o = models.FloatField(null=True)
    base_saturation = models.FloatField(null=True)
    cao_per_mgo = models.FloatField(null=True)
    mgo_per_k2o = models.FloatField(null=True)
    phosphorus_absorption = models.FloatField(null=True)
    p2o5 = models.FloatField(null=True)
    cec = models.FloatField(null=True)
    humus = models.FloatField(null=True)
    bulk_density = models.FloatField(null=True)
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    land_block = models.ForeignKey(LandBlock, on_delete=models.CASCADE)
    land_ledger = models.ForeignKey(LandLedger, on_delete=models.CASCADE)


class LandReview(models.Model):
    """
    顧客が持つ圃場にperiod単位で評価コメントをつける
    remarkはあくまで定型的につけたもの（commentが主体）
    """

    comment = models.TextField()
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    land_ledger = models.ForeignKey(LandLedger, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["land_ledger"], name="land_ledger_unique"),
        ]


class Device(models.Model):
    """
    土壌硬度計マスタ
    """

    name = models.CharField(max_length=256)
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class SoilHardnessMeasurement(models.Model):
    """
    土壌硬度測定 生データ
    """

    set_memory = models.IntegerField()
    set_datetime = models.DateTimeField()
    set_depth = models.IntegerField()
    set_spring = models.IntegerField()
    set_cone = models.IntegerField()
    depth = models.IntegerField()
    pressure = models.IntegerField()
    folder = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)
    set_device = models.ForeignKey(Device, on_delete=models.CASCADE)
    land_block = models.ForeignKey(LandBlock, null=True, on_delete=models.CASCADE)
    land_ledger = models.ForeignKey(LandLedger, null=True, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["set_device", "set_memory", "set_datetime", "depth"],
                name="device_memory_datetime_depth_unique",
            ),
        ]


class SoilHardnessMeasurementImportErrors(models.Model):
    """
    土壌硬度測定 生データ 取り込みエラーリスト
    """

    file = models.CharField(max_length=256)
    folder = models.CharField(max_length=256)
    message = models.TextField()
    remark = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class RouteSuggestImport(models.Model):
    """
    KMLの圃場座標リストをいったん保存するテーブル
    """

    name = models.CharField(max_length=256)
    coords = models.CharField(max_length=256)
    ordering = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class JmaArea(models.Model):
    """
    an area in the JMA
    生データでは center という名前で取り扱われている

    Attributes:
        code (str): エリアコード
        name (str): エリア名
    """

    code = models.CharField(unique=True, max_length=6)
    name = models.CharField(max_length=100)


class JmaPrefecture(models.Model):
    """
    a prefecture in the JMA
    生データでは office という名前で取り扱われている

    Attributes:
        code (CharField): 都道府県コード
        jma_area (ForeignKey): FK to JmaArea
        name (CharField): 都道府県名
    """

    code = models.CharField(unique=True, max_length=6)
    jma_area = models.ForeignKey(JmaArea, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaRegion(models.Model):
    """
    a region in the JMA
    生データでは class10 という名前で取り扱われている

    Attributes:
        code (str): リージョンコード
        jma_prefecture (JmaPrefecture): FK to JmaPrefecture
        name (str): リージョン名
    """

    code = models.CharField(unique=True, max_length=6)
    jma_prefecture = models.ForeignKey(JmaPrefecture, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaCity(models.Model):
    """
    a city in the JMA
    生データでは class20 という名前で取り扱われている

    Attributes:
        code (str): 市区町村コード
        jma_region (JmaRegion): FK to JMA region
        name (str): 市区町村名
    """

    code = models.CharField(unique=True, max_length=7)
    jma_region = models.ForeignKey(JmaRegion, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class JmaAmedas(models.Model):
    """
    a AMeDas in the JMA

    Attributes:
        code (str): アメダス観測所コード
        jma_region (JmaRegion): FK to JMA region
    """

    code = models.CharField(unique=True, max_length=5)
    jma_region = models.ForeignKey(JmaRegion, on_delete=models.CASCADE)


class JmaWeatherCode(models.Model):
    """
    天気コードマスタ

    Attributes:
        code (CharField): "123"
        summary_code (CharField): "100"
        image (FileField): "100.svg"
        name (CharField): "晴"
        name_en (CharField): "CLEAR, FREQUENT SNOW FLURRIES LATER"
    """

    code = models.CharField(unique=True, max_length=3)
    summary_code = models.CharField(max_length=3)
    image = models.CharField(max_length=7)
    name = models.CharField(max_length=20)
    name_en = models.CharField(max_length=100)


class JmaWeather(models.Model):
    """
    日々の天気（1時間ごとにバッチで取得）

    See Also: https://www.jma.go.jp/bosai/forecast/#area_type=class20s&area_code=2820100

    Attributes:
        jma_region (ForeignKey[JmaRegion]): The JMA region associated with the weather data.
        weather_code (CharField): 天気コード
        temperature_min (FloatField): 最低気温
        temperature_max (FloatField): 最高気温
        wind_speed_max (FloatField): 最大風速
    """

    jma_region = models.ForeignKey(JmaRegion, on_delete=models.CASCADE)
    weather_code = models.CharField(max_length=3)
    temperature_min = models.FloatField()
    temperature_max = models.FloatField()
    wind_speed_max = models.FloatField()


class JmaWarning(models.Model):
    """
    Model representing a JMA warning.

    See Also: https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code=2810000&lang=ja

    Attributes:
        jma_region (ForeignKey): The JMA region associated with the warning.
        warnings (CharField): The description of the warning.
    """

    jma_region = models.ForeignKey(JmaRegion, on_delete=models.CASCADE)
    warnings = models.CharField(max_length=100)
