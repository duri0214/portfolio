from collections import Counter, defaultdict

from soil_analysis.domain.valueobject.prefecture_commercial_area import (
    DispatchCandidateVO,
    PrefectureCommercialAreaDashboardVO,
    PrefectureCommercialAreaVO,
    PrefectureWeatherStatsVO,
    PrefectureWarningStatsVO,
    SalesOpportunityCandidateVO,
    WeatherStatsVO,
)
from soil_analysis.models import JmaPrefecture, JmaWarning, JmaWeather, Land, LandLedger


JAPAN_MAP_PREFECTURES = (
    (1, "北海道"),
    (2, "青森県"),
    (3, "岩手県"),
    (4, "宮城県"),
    (5, "秋田県"),
    (6, "山形県"),
    (7, "福島県"),
    (8, "茨城県"),
    (9, "栃木県"),
    (10, "群馬県"),
    (11, "埼玉県"),
    (12, "千葉県"),
    (13, "東京都"),
    (14, "神奈川県"),
    (15, "新潟県"),
    (16, "富山県"),
    (17, "石川県"),
    (18, "福井県"),
    (19, "山梨県"),
    (20, "長野県"),
    (21, "岐阜県"),
    (22, "静岡県"),
    (23, "愛知県"),
    (24, "三重県"),
    (25, "滋賀県"),
    (26, "京都府"),
    (27, "大阪府"),
    (28, "兵庫県"),
    (29, "奈良県"),
    (30, "和歌山県"),
    (31, "鳥取県"),
    (32, "島根県"),
    (33, "岡山県"),
    (34, "広島県"),
    (35, "山口県"),
    (36, "徳島県"),
    (37, "香川県"),
    (38, "愛媛県"),
    (39, "高知県"),
    (40, "福岡県"),
    (41, "佐賀県"),
    (42, "長崎県"),
    (43, "熊本県"),
    (44, "大分県"),
    (45, "宮崎県"),
    (46, "鹿児島県"),
    (47, "沖縄県"),
)


class PrefectureCommercialAreaService:
    """
    既存の土壌分析データから都道府県別商圏ダッシュボード用のVOを生成します。

    このServiceは、Djangoモデルに保存されている圃場・作付台帳・気象警報を
    トップページで扱いやすい読み取り専用の商圏情報へ変換します。
    `Land` は `JmaCity -> JmaRegion -> JmaPrefecture` の関連をたどり、
    JMAコードの都道府県部分へ集約して商圏へアサインします。気象庁マスタは
    北海道・鹿児島・沖縄などを地方単位で分割するため、画面側の商圏は
    japan-map-js の47都道府県コードを基準に組み立てます。

    DBモデルやマイグレーションは追加せず、既存データを集計して表示する
    PoC用途のServiceです。後続で市場価格、GraphRAG、物流APIなどを接続する
    場合も、画面側は `PrefectureCommercialAreaDashboardVO` を読むだけで済むようにします。
    """

    @classmethod
    def build(cls) -> PrefectureCommercialAreaDashboardVO:
        """
        都道府県別商圏ダッシュボード全体の表示モデルを組み立てます。

        japan-map-js の47都道府県コードを基準に商圏を作るため、JMAマスタが
        地方単位に分割されていても、画面には47都道府県として集約されます。
        圃場が未登録の都道府県も `PrefectureCommercialAreaVO` として返すため、
        「未登録」「稼働」「注意」の状態を日本地図上で欠けなく表現できます。

        Returns:
            PrefectureCommercialAreaDashboardVO: 都道府県別商圏と配車候補を束ねた表示用VO。
        """
        land_stats = cls._build_land_stats()
        crop_stats = cls._build_crop_stats()
        warning_stats = cls._build_warning_stats()
        weather_stats = cls._build_future_weather_stats()

        areas = [
            cls._build_area(
                japan_map_code,
                prefecture_name,
                land_stats,
                crop_stats,
                warning_stats,
                weather_stats,
            )
            for japan_map_code, prefecture_name in JAPAN_MAP_PREFECTURES
        ]
        dispatch_candidates = cls._build_dispatch_candidates(areas)
        sales_opportunity_candidates = cls._build_sales_opportunity_candidates(areas)
        return PrefectureCommercialAreaDashboardVO(
            areas=areas,
            dispatch_candidates=dispatch_candidates,
            sales_opportunity_candidates=sales_opportunity_candidates,
        )

    @staticmethod
    def _build_land_stats() -> dict[int, dict]:
        """
        圃場を都道府県へアサインし、商圏別の基本集計を作ります。

        `Land` 自体は都道府県を直接持たないため、紐づくJMA市区町村から
        リージョン、都道府県へたどります。トップページのKPIと商圏テーブルで
        使う圃場数、企業数、面積合計をここでまとめます。

        Returns:
            dict[int, dict]: JMA都道府県IDをキーにした圃場数・企業ID集合・面積合計。
        """
        stats = defaultdict(
            lambda: {"land_count": 0, "company_ids": set(), "total_area": 0.0}
        )
        lands = Land.objects.select_related(
            "company", "jma_city__jma_region__jma_prefecture"
        )
        for land in lands:
            japan_map_code = PrefectureCommercialAreaService._get_japan_map_code(
                land.jma_city.jma_region.jma_prefecture
            )
            if japan_map_code is None:
                continue
            stats[japan_map_code]["land_count"] += 1
            stats[japan_map_code]["company_ids"].add(land.company_id)
            stats[japan_map_code]["total_area"] += land.area or 0.0
        return stats

    @staticmethod
    def _build_crop_stats() -> dict[int, Counter]:
        """
        作付台帳から都道府県別の主要作物候補を集計します。

        `LandLedger` の作物情報を圃場の都道府県へ寄せることで、各商圏の
        代表的な作物名を表示できるようにします。作付台帳がない商圏は
        後続処理で「未設定」として扱います。

        Returns:
            dict[int, Counter]: JMA都道府県IDをキーにした作物名の出現回数。
        """
        stats = defaultdict(Counter)
        ledgers = LandLedger.objects.select_related(
            "crop", "land__jma_city__jma_region__jma_prefecture"
        )
        for ledger in ledgers:
            japan_map_code = PrefectureCommercialAreaService._get_japan_map_code(
                ledger.land.jma_city.jma_region.jma_prefecture
            )
            if japan_map_code is None:
                continue
            stats[japan_map_code][ledger.crop.name] += 1
        return stats

    @staticmethod
    def _build_warning_stats() -> PrefectureWarningStatsVO:
        """
        気象警報・注意報を都道府県別に集計します。

        `JmaWarning` はJMAリージョンごとに警報・注意報名をカンマ区切りで
        保持します。画面には地域件数ではなく、都道府県内で出ている
        警報・注意報名を重複排除して表示します。

        Returns:
            PrefectureWarningStatsVO: 都道府県コード別の警報・注意報集計。
        """
        warning_stats = PrefectureWarningStatsVO(stats_by_japan_map_code={})
        warnings = JmaWarning.objects.select_related("jma_region__jma_prefecture")
        for warning in warnings:
            japan_map_code = PrefectureCommercialAreaService._get_japan_map_code(
                warning.jma_region.jma_prefecture
            )
            if japan_map_code is None:
                continue
            warning_names = [
                warning_name.strip()
                for warning_name in warning.warnings.split(",")
                if warning_name.strip()
            ]
            warning_stats = warning_stats.add_warning_names(
                japan_map_code, warning_names
            )
        return warning_stats

    @staticmethod
    def _build_future_weather_stats() -> PrefectureWeatherStatsVO:
        """
        一番未来の予報日の天気を都道府県別に集計します。

        JMA予報は今日・明日・明後日など複数日を持つため、全国市場VOでは
        `reporting_date` が最も未来の天気を代表表示として採用します。
        複数リージョンを持つ都道府県でも、まず未来日の天気アイコンが欠けずに
        見えることを優先します。

        Returns:
            PrefectureWeatherStatsVO: 都道府県コード別の代表天気。
        """
        weather_stats = PrefectureWeatherStatsVO(stats_by_japan_map_code={})
        weathers = JmaWeather.objects.select_related(
            "jma_region__jma_prefecture", "jma_weather_code"
        ).order_by("-reporting_date", "-id")
        for weather in weathers:
            japan_map_code = PrefectureCommercialAreaService._get_japan_map_code(
                weather.jma_region.jma_prefecture
            )
            if japan_map_code is None or weather_stats.has_japan_map_code(
                japan_map_code
            ):
                continue
            weather_stats = weather_stats.add_weather(
                japan_map_code,
                WeatherStatsVO(
                    name=weather.jma_weather_code.name,
                    icon_image=weather.jma_weather_code.image,
                    code=weather.jma_weather_code.code,
                    reporting_date=weather.reporting_date.isoformat(),
                ),
            )
        return weather_stats

    @classmethod
    def _build_area(
        cls,
        japan_map_code: int,
        prefecture_name: str,
        land_stats: dict[int, dict],
        crop_stats: dict[int, Counter],
        warning_stats: PrefectureWarningStatsVO,
        weather_stats: PrefectureWeatherStatsVO,
    ) -> PrefectureCommercialAreaVO:
        """
        1都道府県分の集計値を商圏VOへ変換します。

        `PrefectureCommercialAreaVO` はテンプレートでそのまま利用する表示用の値を持つため、
        ここで日本地図ライブラリ用の都道府県コード、状態判定に使うリスクスコア、
        主要作物名までまとめて確定させます。

        Args:
            japan_map_code: japan-map-js が使う都道府県コード。
            prefecture_name: 商圏として表示する47都道府県名。
            land_stats: 都道府県別の圃場集計。
            crop_stats: 都道府県別の作物集計。
            warning_stats: 都道府県別の警報・注意報集計。
            weather_stats: 都道府県別の最新天気情報。

        Returns:
            PrefectureCommercialAreaVO: トップページへ渡す1都道府県分の商圏VO。
        """
        stats = land_stats[japan_map_code]
        warning = warning_stats.get_by_japan_map_code(japan_map_code)
        warning_city_count = warning.region_count
        warning_names = warning.sorted_names
        land_count = stats["land_count"]
        risk_score = cls._calculate_risk_score(land_count, warning_city_count)
        main_crop_name = cls._get_main_crop_name(crop_stats[japan_map_code])
        weather = weather_stats.get_by_japan_map_code(japan_map_code)

        return PrefectureCommercialAreaVO(
            prefecture_id=japan_map_code,
            prefecture_name=prefecture_name,
            japan_map_code=japan_map_code,
            land_count=land_count,
            company_count=len(stats["company_ids"]),
            main_crop_name=main_crop_name,
            total_area=round(stats["total_area"], 2),
            warning_city_count=warning_city_count,
            warning_names=warning_names,
            risk_score=risk_score,
            weather_name=weather.name,
            weather_icon_image=weather.icon_image,
            weather_code=weather.code,
            weather_reporting_date=weather.reporting_date,
        )

    @staticmethod
    def _get_japan_map_code(jma_prefecture: JmaPrefecture) -> int | None:
        """
        JMA都道府県マスタを japan-map-js の47都道府県コードへ変換します。

        気象庁の府県予報区マスタは、北海道を「宗谷地方」「上川・留萌地方」
        のように複数行へ分割します。一方、地図ライブラリは47都道府県の
        コード体系を使うため、JMAコード先頭2桁を都道府県コードとして扱い、
        分割されたJMA行を同じ都道府県へ集約します。

        Args:
            jma_prefecture: 圃場や警報に紐づくJMA都道府県マスタ。

        Returns:
            int: japan-map-js の都道府県コード。

        Raises:
            ValueError: JMAコードから1から47の都道府県コードを取得できない場合。
        """
        try:
            japan_map_code = int(jma_prefecture.code[:2])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"JMA都道府県コードを都道府県コードへ変換できません: "
                f"id={jma_prefecture.id}, code={jma_prefecture.code}, name={jma_prefecture.name}"
            ) from error

        if 1 <= japan_map_code <= 47:
            return japan_map_code
        raise ValueError(
            f"JMA都道府県コードが1から47の都道府県コードに対応していません: "
            f"id={jma_prefecture.id}, code={jma_prefecture.code}, name={jma_prefecture.name}"
        )

    @staticmethod
    def _calculate_risk_score(land_count: int, warning_city_count: int) -> int:
        """
        商圏の表示順と状態表示に使う簡易リスクスコアを算出します。

        警報・注意報がある商圏を最優先で目立たせ、圃場登録だけがある商圏は
        通常稼働として低めのスコアにします。未登録商圏は比較対象として
        地図に残しつつ、リスクは0として扱います。

        Args:
            land_count: 都道府県にアサインされた圃場数。
            warning_city_count: 都道府県内の警報・注意報件数。

        Returns:
            int: 0から100までの簡易リスクスコア。
        """
        if warning_city_count:
            return min(100, 70 + warning_city_count * 5)
        if land_count:
            return 30
        return 0

    @staticmethod
    def _get_main_crop_name(crop_counter: Counter) -> str:
        """
        商圏の代表作物として表示する作物名を選びます。

        作付台帳に紐づく作物のうち最も出現数が多いものを採用します。
        データ未登録の商圏でも画面表示が欠けないよう、空の場合は
        「未設定」を返します。

        Args:
            crop_counter: 作物名ごとの出現回数。

        Returns:
            str: 商圏テーブルや配車候補に表示する主要作物名。
        """
        if not crop_counter:
            return "未設定"
        return crop_counter.most_common(1)[0][0]

    @staticmethod
    def _build_dispatch_candidates(
        areas: list[PrefectureCommercialAreaVO],
    ) -> list[DispatchCandidateVO]:
        """
        商圏集計からトップページ用の出荷候補リストを生成します。

        現時点では外部の市場価格や物流APIへ接続せず、圃場登録がある商圏を
        画面上で確認しやすくするための簡易候補を作ります。警報・注意報がある
        商圏は「天候確認中」とし、通常商圏は出荷候補として表示します。

        Args:
            areas: 都道府県単位の商圏VO一覧。

        Returns:
            list[DispatchCandidateVO]: トップページの配車候補キューに表示する候補。
        """
        active_areas = [area for area in areas if area.land_count]
        sorted_areas = sorted(
            active_areas,
            key=lambda area: (area.warning_city_count == 0, area.land_count),
            reverse=True,
        )

        candidates = []
        for index, area in enumerate(sorted_areas[:5]):
            market_name = "首都圏市場" if index % 2 == 0 else "関西市場"
            logistics_status = (
                "配車候補あり" if not area.warning_city_count else "天候確認中"
            )
            if area.warning_city_count:
                reason = f"{area.prefecture_name}は警報・注意報があるため、代替ルート確認を優先します。"
            else:
                reason = f"{area.prefecture_name}は圃場登録があり、{area.main_crop_name}の出荷候補として監視します。"

            candidates.append(
                DispatchCandidateVO(
                    origin_name=area.prefecture_name,
                    target_market_name=market_name,
                    main_crop_name=area.main_crop_name,
                    logistics_status=logistics_status,
                    reason=reason,
                    risk_score=area.risk_score,
                )
            )
        return candidates

    @classmethod
    def _build_sales_opportunity_candidates(
        cls,
        areas: list[PrefectureCommercialAreaVO],
    ) -> list[SalesOpportunityCandidateVO]:
        """
        赤信号商圏へ他都道府県から売り込む候補リストを生成します。

        警報・注意報がある商圏を「出荷側として止まっている地域」とみなし、
        警報・注意報がなく圃場登録のある他商圏を売り込み元候補にします。
        A県→B県とB県→A県は別々の関係として扱うため、候補は一方向のVOで返します。

        Args:
            areas: 都道府県単位の商圏VO一覧。

        Returns:
            list[SalesOpportunityCandidateVO]: 神視点オッズつきの売り込み候補。
        """
        target_areas = [area for area in areas if area.warning_city_count]
        origin_areas = [
            area for area in areas if area.land_count and not area.warning_city_count
        ]
        candidates = []
        for target_area in target_areas:
            for origin_area in origin_areas:
                if origin_area.japan_map_code == target_area.japan_map_code:
                    continue
                odds_score = cls._calculate_god_odds_score(origin_area, target_area)
                candidates.append(
                    SalesOpportunityCandidateVO(
                        origin_name=origin_area.prefecture_name,
                        target_name=target_area.prefecture_name,
                        main_crop_name=origin_area.main_crop_name,
                        odds_score=odds_score,
                        odds_label=cls._get_odds_label(odds_score),
                        relation_label=(
                            f"{origin_area.prefecture_name}→"
                            f"{target_area.prefecture_name}"
                        ),
                        reason=cls._build_sales_opportunity_reason(
                            origin_area, target_area
                        ),
                    )
                )

        return sorted(
            candidates,
            key=lambda candidate: candidate.odds_score,
            reverse=True,
        )[:5]

    @classmethod
    def _calculate_god_odds_score(
        cls,
        origin_area: PrefectureCommercialAreaVO,
        target_area: PrefectureCommercialAreaVO,
    ) -> int:
        """
        神視点でA県→B県の売り込みオッズを単一スコアとして算出します。

        天気コードの先頭1桁をカテゴリとして係数化し、警報・注意報件数と
        組み合わせて1つの値へ畳み込みます。

        Args:
            origin_area: 売り込み元商圏。
            target_area: 赤信号として売り込み先候補になる商圏。

        Returns:
            int: 0から100までの神視点オッズ。
        """
        weather_factor = cls._get_weather_factor(target_area.weather_code)
        warning_score = min(60, target_area.warning_city_count * 20)
        odds_score = int(round((35 + warning_score) * weather_factor))
        return min(100, odds_score)

    @staticmethod
    def _get_weather_factor(weather_code: str) -> float:
        """
        JMA天気コード先頭1桁からオッズ係数を返します。

        Args:
            weather_code: JMA天気コード。

        Returns:
            float: 晴れ、曇り、雨・雪、未取得を区別する係数。
        """
        if weather_code.startswith("3") or weather_code.startswith("4"):
            return 1.25
        if weather_code.startswith("2"):
            return 1.0
        if weather_code.startswith("1"):
            return 0.8
        return 0.9

    @staticmethod
    def _get_odds_label(odds_score: int) -> str:
        """
        神視点オッズの画面表示ラベルを返します。

        Args:
            odds_score: 神視点で発行された0から100までの単一オッズ。

        Returns:
            str: 高オッズ、中オッズ、低オッズのいずれか。
        """
        if odds_score >= 80:
            return "高オッズ"
        if odds_score >= 60:
            return "中オッズ"
        return "低オッズ"

    @classmethod
    def _build_sales_opportunity_reason(
        cls,
        origin_area: PrefectureCommercialAreaVO,
        target_area: PrefectureCommercialAreaVO,
    ) -> str:
        """
        売り込み候補の判断理由を画面表示用に組み立てます。

        Args:
            origin_area: 売り込み元商圏。
            target_area: 売り込み先商圏。

        Returns:
            str: オッズに寄与した判断軸を含む説明文。
        """
        return (
            f"{target_area.prefecture_name}は{target_area.warning_summary}で赤信号。"
            f"{origin_area.prefecture_name}は警報・注意報がないため、"
            f"{target_area.prefecture_name}への売り込み候補になります。"
        )
