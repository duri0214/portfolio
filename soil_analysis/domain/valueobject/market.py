from dataclasses import dataclass


@dataclass(frozen=True)
class CommercialAreaVO:
    """
    都道府県単位の農業商圏を表す読み取り専用VOです。

    `soil_analysis` のトップページでは、日本地図グリッド上の1マスと
    全国市場VOテーブルの1行がこのVOに対応します。既存の圃場は
    `JmaCity -> JmaRegion -> JmaPrefecture` の関連を通じて都道府県へ
    アサインされ、その集計結果をこのVOが保持します。

    DBへ保存するためのモデルではなく、Serviceが集計した値をテンプレートへ
    安定して渡すための表示境界です。圃場が未登録の都道府県もVOとして保持し、
    「未登録」「稼働」「注意」の状態を画面上で欠けなく表現します。

    Attributes:
        prefecture_id: JMA都道府県マスタのID。
        prefecture_name: 都道府県名。
        land_count: 登録済み圃場数。
        company_count: 登録済み農業法人・企業数。
        main_crop_name: 最も多く台帳に登場する作物名。
        total_area: 圃場面積の合計。
        warning_city_count: 警報・注意報が登録されている市区町村数。
        risk_score: 商圏リスクスコア。警報と登録データ有無から算出する。
        map_row: 簡易日本地図グリッドの行番号。
        map_col: 簡易日本地図グリッドの列番号。
    """

    prefecture_id: int
    prefecture_name: str
    land_count: int
    company_count: int
    main_crop_name: str
    total_area: float
    warning_city_count: int
    risk_score: int
    map_row: int
    map_col: int

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
    def map_position_class(self) -> str:
        """
        日本地図グリッド上の配置に使うCSSクラス名を返します。

        行番号と列番号をCSSクラスへ変換し、テンプレートはこの値を付与するだけで
        都道府県タイルを所定の位置へ配置できます。

        Returns:
            str: `map-row-<行番号> map-col-<列番号>` 形式のCSSクラス名。
        """
        return f"map-row-{self.map_row} map-col-{self.map_col}"


@dataclass(frozen=True)
class DispatchCandidateVO:
    """
    商圏から仮想市場への出荷候補を表す読み取り専用VOです。

    このVOは、全国商圏マップの右側に表示する配車候補キューのために使います。
    現段階では実在の物流APIや市場価格へ接続せず、圃場登録のある商圏を
    「どこから、どの市場へ、どの作物を出せそうか」という形で可視化する
    PoC用の表示モデルです。

    後続で市況データや配車APIに置き換える場合も、テンプレート側はこのVOを
    読むだけにしておくことで、外部連携の差し替え範囲をService側へ閉じます。

    Attributes:
        origin_name: 出荷元の都道府県商圏名。
        target_market_name: 仮想の出荷先市場名。
        main_crop_name: 出荷候補の主要作物名。
        logistics_status: 配車候補の状態。
        reason: 推奨理由。
        risk_score: 対象商圏のリスクスコア。
    """

    origin_name: str
    target_market_name: str
    main_crop_name: str
    logistics_status: str
    reason: str
    risk_score: int


@dataclass(frozen=True)
class NationalMarketVO:
    """
    47都道府県の商圏を束ねた全国市場ビューを表す読み取り専用VOです。

    `CommercialAreaVO` の一覧をアプリケーション画面へ渡す集約ルートとして扱います。
    トップページのKPI、日本地図、都道府県別テーブル、配車候補キューは
    このVOから派生した値だけを参照します。

    画面表示に必要な集計プロパティをここへまとめることで、テンプレート内の
    分岐や集計処理を減らし、将来GraphRAG・市場価格・物流APIを追加しても
    表示側の契約を保ちやすくします。

    Attributes:
        areas: 都道府県単位の商圏一覧。
        dispatch_candidates: 出荷候補一覧。
    """

    areas: list[CommercialAreaVO]
    dispatch_candidates: list[DispatchCandidateVO]

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
        全国商圏にアサインされた圃場数の合計を返します。

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
    def featured_areas(self) -> list[CommercialAreaVO]:
        """
        全国市場VOテーブルに優先表示する商圏を返します。

        リスクスコア、圃場数、企業数の順に並べることで、確認優先度の高い
        都道府県をトップページ上で目に入りやすくします。

        Returns:
            list[CommercialAreaVO]: 優先表示する最大8件の商圏VO。
        """
        return sorted(
            self.areas,
            key=lambda area: (area.risk_score, area.land_count, area.company_count),
            reverse=True,
        )[:8]
