from dataclasses import dataclass


@dataclass(frozen=True)
class WarningStatsVO:
    """
    都道府県単位の警報・注意報集計を表す読み取り専用VOです。

    `JmaWarning` はJMAリージョン単位のデータですが、トップページでは
    japan-map-js の47都道府県単位へ集約して扱います。このVOは、警報・注意報が
    登録されている地域数と、重複排除済みの警報・注意報名を保持します。

    Attributes:
        region_count: 警報・注意報が登録されているJMAリージョン数。
        names: 都道府県内で発表されている警報・注意報名。
    """

    region_count: int
    names: frozenset[str]

    def add_names(self, warning_names: list[str]) -> "WarningStatsVO":
        """
        1リージョン分の警報・注意報名を加算した新しいVOを返します。

        Args:
            warning_names: カンマ区切り文字列から取り出した警報・注意報名。

        Returns:
            WarningStatsVO: 地域数と警報・注意報名を更新した集計VO。
        """
        return WarningStatsVO(
            region_count=self.region_count + 1,
            names=self.names | frozenset(warning_names),
        )

    @property
    def sorted_names(self) -> list[str]:
        """
        画面表示に使いやすい順序へ並べた警報・注意報名を返します。

        Returns:
            list[str]: 名前順に並べた警報・注意報名。
        """
        return sorted(self.names)


@dataclass(frozen=True)
class PrefectureWarningStatsVO:
    """
    都道府県コード別の警報・注意報集計を束ねる読み取り専用VOです。

    `stats_by_japan_map_code` のキーは japan-map-js が使う1から47の
    都道府県コードです。Service側に `dict[int, WarningStatsVO]` を露出させず、
    コードの意味と未登録時の初期値をこのVOへ閉じ込めます。

    Attributes:
        stats_by_japan_map_code: japan-map-js 都道府県コードごとの警報・注意報集計。
    """

    stats_by_japan_map_code: dict[int, WarningStatsVO]

    def add_warning_names(
        self, japan_map_code: int, warning_names: list[str]
    ) -> "PrefectureWarningStatsVO":
        """
        指定した都道府県コードへ1リージョン分の警報・注意報名を加算します。

        Args:
            japan_map_code: japan-map-js が使う1から47の都道府県コード。
            warning_names: カンマ区切り文字列から取り出した警報・注意報名。

        Returns:
            PrefectureWarningStatsVO: 指定都道府県の集計を更新した新しいVO。
        """
        current_stats = self.get_by_japan_map_code(japan_map_code)
        next_stats = current_stats.add_names(warning_names)
        return PrefectureWarningStatsVO(
            stats_by_japan_map_code={
                **self.stats_by_japan_map_code,
                japan_map_code: next_stats,
            }
        )

    def get_by_japan_map_code(self, japan_map_code: int) -> WarningStatsVO:
        """
        指定した都道府県コードの警報・注意報集計を返します。

        Args:
            japan_map_code: japan-map-js が使う1から47の都道府県コード。

        Returns:
            WarningStatsVO: 指定都道府県の警報・注意報集計。未登録の場合は空の集計。
        """
        return self.stats_by_japan_map_code.get(
            japan_map_code, WarningStatsVO(region_count=0, names=frozenset())
        )


@dataclass(frozen=True)
class WeatherStatsVO:
    """
    都道府県単位の代表天気を表す読み取り専用VOです。

    JMA予報のうち、トップページで代表表示に使う一番未来の予報日だけを
    都道府県単位へ集約して保持します。

    Attributes:
        name: 代表表示する天気名称。
        icon_image: 代表表示する天気アイコンファイル名。
        code: 代表表示する天気コード。
        reporting_date: 代表表示する予報日。
    """

    name: str
    icon_image: str
    code: str
    reporting_date: str


@dataclass(frozen=True)
class PrefectureWeatherStatsVO:
    """
    都道府県コード別の代表天気を束ねる読み取り専用VOです。

    `stats_by_japan_map_code` のキーは japan-map-js が使う1から47の
    都道府県コードです。Service側に `dict[int, dict[str, str]]` を露出させず、
    コードの意味と天気情報の項目をこのVOへ閉じ込めます。

    Attributes:
        stats_by_japan_map_code: japan-map-js 都道府県コードごとの代表天気。
    """

    stats_by_japan_map_code: dict[int, WeatherStatsVO]

    def add_weather(
        self, japan_map_code: int, weather: WeatherStatsVO
    ) -> "PrefectureWeatherStatsVO":
        """
        指定した都道府県コードへ代表天気を追加します。

        Args:
            japan_map_code: japan-map-js が使う1から47の都道府県コード。
            weather: 都道府県の代表天気。

        Returns:
            PrefectureWeatherStatsVO: 指定都道府県の代表天気を追加した新しいVO。
        """
        return PrefectureWeatherStatsVO(
            stats_by_japan_map_code={
                **self.stats_by_japan_map_code,
                japan_map_code: weather,
            }
        )

    def has_japan_map_code(self, japan_map_code: int) -> bool:
        """
        指定した都道府県コードの代表天気が登録済みかを返します。

        Args:
            japan_map_code: japan-map-js が使う1から47の都道府県コード。

        Returns:
            bool: 代表天気が登録済みの場合はTrue。
        """
        return japan_map_code in self.stats_by_japan_map_code

    def get_by_japan_map_code(self, japan_map_code: int) -> WeatherStatsVO:
        """
        指定した都道府県コードの代表天気を返します。

        Args:
            japan_map_code: japan-map-js が使う1から47の都道府県コード。

        Returns:
            WeatherStatsVO: 指定都道府県の代表天気。未登録の場合は天気未取得。
        """
        return self.stats_by_japan_map_code.get(
            japan_map_code,
            WeatherStatsVO(
                name="天気未取得", icon_image="", code="", reporting_date=""
            ),
        )


@dataclass(frozen=True)
class PrefectureCommercialAreaVO:
    """
    都道府県単位の農業商圏を表す読み取り専用VOです。

    `soil_analysis` のトップページでは、japan-map-js 上の1都道府県と
    全国商圏リスクランキングの1行がこのVOに対応します。既存の圃場は
    `JmaCity -> JmaRegion -> JmaPrefecture` の関連を通じて都道府県へ
    アサインされ、その集計結果をこのVOが保持します。

    DBへ保存するためのモデルではなく、Serviceが集計した値をテンプレートへ
    安定して渡すための表示用データ構造です。圃場が未登録の都道府県もVOとして保持し、
    「未登録」「稼働」「注意」の状態を画面上で欠けなく表現します。

    Attributes:
        prefecture_id: 47都道府県として扱う表示用ID。japan-map-js のコードと同じ値。
        prefecture_name: 都道府県名。
        japan_map_code: japan-map-js が都道府県識別に使う1から47のコード。
        jma_area_code: JMAの大きい地域コード。
        jma_area_name: JMAの大きい地域名。
        land_count: 登録済み圃場数。
        company_count: 登録済み農業法人・企業数。
        main_crop_name: 最も多く台帳に登場する代表作物名。
        crop_names: 作付台帳に登場する作物名一覧。
        total_area: 圃場面積の合計。
        warning_city_count: 警報・注意報が登録されている市区町村数。
        warning_names: 都道府県内で発表されている警報・注意報名。
        risk_score: 商圏リスクスコア。警報と登録データ有無から算出する。
        weather_risk_index: 天気と警報・注意報から算出した出荷リスク指数。
        weather_name: 一番未来の予報日の天気名称。
        weather_icon_image: 一番未来の予報日の天気アイコンファイル名。
        weather_code: 一番未来の予報日の天気コード。
        weather_reporting_date: 一番未来の予報日。
    """

    prefecture_id: int
    prefecture_name: str
    japan_map_code: int
    jma_area_code: str
    jma_area_name: str
    land_count: int
    company_count: int
    main_crop_name: str
    crop_names: list[str]
    total_area: float
    warning_city_count: int
    warning_names: list[str]
    risk_score: int
    weather_risk_index: float
    weather_name: str
    weather_icon_image: str
    weather_code: str
    weather_reporting_date: str

    @property
    def status_label(self) -> str:
        """
        商圏マップと一覧に表示する状態ラベルを返します。

        警報・注意報がある商圏は圃場数に関係なく「注意」とし、警報がなく
        圃場がある商圏は「稼働」、圃場がない商圏は「未登録」として扱います。

        Returns:
            str: 画面に表示する商圏状態。
        """
        if self.warning_city_count:
            return "注意"
        if self.land_count:
            return "稼働"
        return "未登録"

    @property
    def status_class(self) -> str:
        """
        商圏状態に対応するCSSクラス名を返します。

        テンプレート側で状態判定を繰り返さないよう、表示色の選択に必要な
        クラス名をVOで提供します。

        Returns:
            str: `area-risk`、`area-active`、`area-empty` のいずれか。
        """
        if self.warning_city_count:
            return "area-risk"
        if self.land_count:
            return "area-active"
        return "area-empty"

    @property
    def warning_summary(self) -> str:
        """
        画面表示用の警報・注意報サマリを返します。

        Returns:
            str: 警報・注意報名の列記。未発表の場合は `なし`。
        """
        if not self.warning_names:
            return "なし"
        return "、".join(self.warning_names)

    @property
    def crop_summary(self) -> str:
        """
        画面表示用の作物サマリを返します。

        Returns:
            str: 作物名の列記。未登録の場合は `未設定`。
        """
        if not self.crop_names:
            return "未設定"
        return "、".join(self.crop_names)

    @property
    def map_payload(self) -> dict[str, int | str]:
        """
        japan-map-js に渡す都道府県別データを返します。

        ライブラリ側は `code` で都道府県を特定します。集計値はクリック時の
        詳細表示に使うため、同じJSONへ含めます。

        Returns:
            dict[str, int | str]: 日本地図描画とクリック詳細に使う都道府県データ。
        """
        return {
            "code": self.japan_map_code,
            "name": self.prefecture_name,
            "jmaAreaName": self.jma_area_name,
            "status": self.status_label,
            "statusClass": self.status_class,
            "landCount": self.land_count,
            "companyCount": self.company_count,
            "mainCropName": self.main_crop_name,
            "cropSummary": self.crop_summary,
            "warningCount": self.warning_city_count,
            "warningSummary": self.warning_summary,
            "riskScore": self.risk_score,
            "weatherRiskIndex": self.weather_risk_index,
            "weatherName": self.weather_name,
            "weatherIconImage": self.weather_icon_image,
            "weatherCode": self.weather_code,
            "weatherReportingDate": self.weather_reporting_date,
        }


@dataclass(frozen=True)
class DispatchCandidateVO:
    """
    都道府県間の一人称商圏に基づく配車候補を表す読み取り専用VOです。

    このVOは、都道府県別商圏マップの右側に表示する配車候補キューのために使います。
    現段階では実在の物流APIや市場価格へ接続せず、天気リスクが高い都道府県へ
    他都道府県が同じ登録作物を売り込む関係を配車の確認対象として可視化します。

    後続で市況データや配車APIに置き換える場合も、テンプレート側はこのVOを
    読むだけにしておくことで、外部連携の差し替え範囲をService側へ閉じます。

    Attributes:
        origin_name: 売り込み元の都道府県名。
        target_prefecture_name: 天気リスクが高い売り込み先の都道府県名。
        main_crop_name: 出荷候補として一致した作物名。
        logistics_status: 配車候補の状態。
        reason: 推奨理由。
        weather_risk_index: 売り込み先都道府県の天気リスク指数。
        relation_label: A県→B県を示す一方向の商圏関係ラベル。
    """

    origin_name: str
    target_prefecture_name: str
    main_crop_name: str
    logistics_status: str
    reason: str
    weather_risk_index: float
    relation_label: str


@dataclass(frozen=True)
class SalesOpportunityCandidateVO:
    """
    天気リスクが高い商圏へ他県が売り込みをかける候補関係を表す読み取り専用VOです。

    このVOは、売り込み先の天気と警報・注意報から算出した
    出荷リスク指数を保持します。都道府県自身が自己申告する値ではなく、
    A県からB県へ売り込む一方向の商圏関係として扱います。

    Attributes:
        origin_name: 売り込み元の都道府県名。
        target_name: 天気リスクが高く売り込み先候補になる都道府県名。
        main_crop_name: 売り込み候補として一致した作物名。
        weather_risk_index: 天気と警報・注意報から算出した出荷リスク指数。
        origin_weather_risk_index: 売り込み元都道府県の天気リスク指数。
        is_same_jma_area: 売り込み元と売り込み先が同じJMA地域かどうか。
        relation_label: A県→B県を示す一方向の商圏関係ラベル。
        reason: リスク指数に寄与した主な判断材料。
    """

    origin_name: str
    target_name: str
    main_crop_name: str
    weather_risk_index: float
    origin_weather_risk_index: float
    is_same_jma_area: bool
    relation_label: str
    reason: str


@dataclass(frozen=True)
class PrefectureCommercialAreaDashboardVO:
    """
    47都道府県の商圏を束ねた都道府県別商圏ビューを表す読み取り専用VOです。

    `PrefectureCommercialAreaVO` の一覧をアプリケーション画面へ渡す集約ルートとして扱います。
    トップページのKPI、日本地図、都道府県別テーブル、配車候補キューは
    このVOから派生した値だけを参照します。

    画面表示に必要な集計プロパティをここへまとめることで、テンプレート内の
    分岐や集計処理を減らし、将来GraphRAG・市場価格・物流APIを追加しても
    表示側の契約を保ちやすくします。

    Attributes:
        areas: 都道府県単位の商圏一覧。
        dispatch_candidates: 都道府県間の配車候補一覧。
        sales_opportunity_candidates: 天気リスクが高い商圏への売り込み候補一覧。
    """

    areas: list[PrefectureCommercialAreaVO]
    dispatch_candidates: list[DispatchCandidateVO]
    sales_opportunity_candidates: list[SalesOpportunityCandidateVO]

    @property
    def area_count(self) -> int:
        """
        表示対象となる商圏数を返します。

        Returns:
            int: JMA都道府県マスタを基準に作成された商圏数。
        """
        return len(self.areas)

    @property
    def active_area_count(self) -> int:
        """
        圃場が1件以上アサインされている商圏数を返します。

        Returns:
            int: 稼働中または注意状態の商圏数。
        """
        return sum(1 for area in self.areas if area.land_count)

    @property
    def risk_area_count(self) -> int:
        """
        警報・注意報がある商圏数を返します。

        Returns:
            int: 注意状態として扱う商圏数。
        """
        return sum(1 for area in self.areas if area.warning_city_count)

    @property
    def land_count(self) -> int:
        """
        都道府県別商圏にアサインされた圃場数の合計を返します。

        Returns:
            int: 全都道府県の登録済み圃場数。
        """
        return sum(area.land_count for area in self.areas)

    @property
    def dispatch_candidate_count(self) -> int:
        """
        トップページに表示する配車候補数を返します。

        Returns:
            int: 生成済みの配車候補VO数。
        """
        return len(self.dispatch_candidates)

    @property
    def sales_opportunity_candidate_count(self) -> int:
        """
        トップページに表示する売り込み候補数を返します。

        Returns:
            int: 生成済みの売り込み候補VO数。
        """
        return len(self.sales_opportunity_candidates)

    @property
    def areas_by_weather_risk(self) -> list[PrefectureCommercialAreaVO]:
        """
        全国商圏リスクランキングに表示する商圏をリスク指数降順で返します。

        天気が悪い地域ほどリスク指数が高くなるため、指数の高い
        都道府県を上から確認できるようにします。同じ指数の場合は
        圃場数、企業数、都道府県コードの順で表示順を安定させます。

        Returns:
            list[PrefectureCommercialAreaVO]: リスク指数降順に並べた全商圏VO。
        """
        return sorted(
            self.areas,
            key=lambda area: (
                area.weather_risk_index,
                area.land_count,
                area.company_count,
                -area.japan_map_code,
            ),
            reverse=True,
        )

    @property
    def map_payload(self) -> list[dict[str, int | str]]:
        """
        japan-map-js に渡す都道府県別商圏データを返します。

        テンプレートではこの値を `json_script` で埋め込み、JavaScript側で
        都道府県ごとの色分けとクリック時の詳細表示に利用します。

        Returns:
            list[dict[str, int | str]]: 47都道府県分の日本地図描画データ。
        """
        return [area.map_payload for area in self.areas]
