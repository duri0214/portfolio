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

HIGH_WEATHER_RISK_INDEX = 4.0


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
        jma_area_stats = cls._build_jma_area_stats()
        warning_stats = cls._build_warning_stats()
        weather_stats = cls._build_future_weather_stats()

        areas = [
            cls._build_area(
                japan_map_code,
                prefecture_name,
                land_stats,
                crop_stats,
                jma_area_stats,
                warning_stats,
                weather_stats,
            )
            for japan_map_code, prefecture_name in JAPAN_MAP_PREFECTURES
        ]
        sales_opportunity_candidates = cls._build_sales_opportunity_candidates(areas)
        dispatch_candidates = cls._build_dispatch_candidates(
            sales_opportunity_candidates
        )
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
    def _build_jma_area_stats() -> dict[int, dict[str, str]]:
        """
        JMA都道府県マスタから47都道府県ごとの大きい地域を集計します。

        JMAの `area` は東北地方、近畿地方のような大きい地域を表します。
        売り込み候補の近さ判定では、都道府県名をハードコードせず、
        同じJMA地域に属するかを使います。

        Returns:
            dict[int, dict[str, str]]: japan-map-js コードごとのJMA地域コードと地域名。
        """
        stats = {}
        prefectures = JmaPrefecture.objects.select_related("jma_area")
        for prefecture in prefectures:
            japan_map_code = PrefectureCommercialAreaService._get_japan_map_code(
                prefecture
            )
            if japan_map_code is None or japan_map_code in stats:
                continue
            stats[japan_map_code] = {
                "code": prefecture.jma_area.code,
                "name": prefecture.jma_area.name,
            }
        return stats

    @staticmethod
    def _build_crop_stats() -> dict[int, Counter]:
        """
        作付台帳から都道府県別の登録作物を集計します。

        `LandLedger` の作物情報を圃場の都道府県へ寄せることで、各商圏の
        登録作物名を表示できるようにします。作付台帳がない商圏は
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
        jma_area_stats: dict[int, dict[str, str]],
        warning_stats: PrefectureWarningStatsVO,
        weather_stats: PrefectureWeatherStatsVO,
    ) -> PrefectureCommercialAreaVO:
        """
        1都道府県分の集計値を商圏VOへ変換します。

        `PrefectureCommercialAreaVO` はテンプレートでそのまま利用する表示用の値を持つため、
        ここで日本地図ライブラリ用の都道府県コード、状態判定に使うリスクスコア、
        登録作物名までまとめて確定させます。

        Args:
            japan_map_code: japan-map-js が使う都道府県コード。
            prefecture_name: 商圏として表示する47都道府県名。
            land_stats: 都道府県別の圃場集計。
            crop_stats: 都道府県別の作物集計。
            jma_area_stats: 都道府県別のJMA地域集計。
            warning_stats: 都道府県別の警報・注意報集計。
            weather_stats: 都道府県別の最新天気情報。

        Returns:
            PrefectureCommercialAreaVO: トップページへ渡す1都道府県分の商圏VO。
        """
        stats = land_stats[japan_map_code]
        jma_area = jma_area_stats.get(japan_map_code, {"code": "", "name": ""})
        warning = warning_stats.get_by_japan_map_code(japan_map_code)
        warning_city_count = warning.region_count
        warning_names = warning.sorted_names
        land_count = stats["land_count"]
        risk_score = cls._calculate_risk_score(land_count, warning_city_count)
        crop_names = cls._get_crop_names(crop_stats[japan_map_code])
        main_crop_name = crop_names[0] if crop_names else "未設定"
        weather = weather_stats.get_by_japan_map_code(japan_map_code)
        weather_risk_index = cls._calculate_weather_risk_index(
            weather.code, warning_city_count
        )

        return PrefectureCommercialAreaVO(
            prefecture_id=japan_map_code,
            prefecture_name=prefecture_name,
            japan_map_code=japan_map_code,
            jma_area_code=jma_area["code"],
            jma_area_name=jma_area["name"],
            land_count=land_count,
            company_count=len(stats["company_ids"]),
            main_crop_name=main_crop_name,
            crop_names=crop_names,
            total_area=round(stats["total_area"], 2),
            warning_city_count=warning_city_count,
            warning_names=warning_names,
            risk_score=risk_score,
            weather_risk_index=weather_risk_index,
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
    def _get_crop_names(crop_counter: Counter) -> list[str]:
        """
        商圏の作物名を出現数順に返します。

        作付台帳に紐づく作物を、出現数が多い順、同数の場合は名前順で返します。
        データ未登録の商圏は空のリストとして扱います。

        Args:
            crop_counter: 作物名ごとの出現回数。

        Returns:
            list[str]: 商圏テーブルや配車候補判定に使う作物名一覧。
        """
        if not crop_counter:
            return []
        return [
            crop_name
            for crop_name, _ in sorted(
                crop_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    @staticmethod
    def _build_dispatch_candidates(
        sales_opportunity_candidates: list[SalesOpportunityCandidateVO],
    ) -> list[DispatchCandidateVO]:
        """
        売り込み候補からトップページ用の配車候補リストを生成します。

        天気リスクが高い都道府県へ他都道府県が売り込む関係を、
        配車調整で確認する一方向のキューとして扱います。商圏リスクスコアではなく、
        売り込み先の天気リスク指数を判断軸にします。

        Args:
            sales_opportunity_candidates: 天気リスクが高い商圏への売り込み候補一覧。

        Returns:
            list[DispatchCandidateVO]: トップページの配車候補キューに表示する候補。
        """
        candidates = []
        for candidate in sales_opportunity_candidates[:5]:
            reason = (
                f"{candidate.target_name}の天気リスクを見て、"
                f"{candidate.origin_name}からの代替出荷便を確認します。"
            )
            candidates.append(
                DispatchCandidateVO(
                    origin_name=candidate.origin_name,
                    target_prefecture_name=candidate.target_name,
                    main_crop_name=candidate.main_crop_name,
                    logistics_status="代替便確認中",
                    reason=reason,
                    weather_risk_index=candidate.weather_risk_index,
                    relation_label=candidate.relation_label,
                )
            )
        return candidates

    @classmethod
    def _build_sales_opportunity_candidates(
        cls,
        areas: list[PrefectureCommercialAreaVO],
    ) -> list[SalesOpportunityCandidateVO]:
        """
        天気リスクが高い商圏へ同じ登録作物を持つ他都道府県から売り込む候補リストを生成します。

        雨・雪や警報・注意報で天気リスク指数が高い商圏を
        「登録作物の出荷が止まりやすい地域」とみなし、同じ登録作物を持ち、
        対象より天気リスク指数が低い他商圏を売り込み元候補にします。
        隣接県が候補になる場合は、遠方県より優先します。
        ここでいう隣接県は、JMAの大きい地域が同じ都道府県として扱います。
        A県→B県とB県→A県は別々の関係として扱うため、候補は一方向のVOで返します。

        Args:
            areas: 都道府県単位の商圏VO一覧。

        Returns:
            list[SalesOpportunityCandidateVO]: リスク指数つきの売り込み候補。
        """
        target_areas = [
            area
            for area in areas
            if area.weather_risk_index >= HIGH_WEATHER_RISK_INDEX and area.crop_names
        ]
        origin_areas = [area for area in areas if area.land_count and area.crop_names]
        candidates = []
        for target_area in target_areas:
            for origin_area in origin_areas:
                if origin_area.japan_map_code == target_area.japan_map_code:
                    continue
                if origin_area.weather_risk_index >= target_area.weather_risk_index:
                    continue
                matched_crop_names = sorted(
                    set(origin_area.crop_names) & set(target_area.crop_names)
                )
                if not matched_crop_names:
                    continue
                matched_crop_name = matched_crop_names[0]
                candidates.append(
                    SalesOpportunityCandidateVO(
                        origin_name=origin_area.prefecture_name,
                        target_name=target_area.prefecture_name,
                        main_crop_name=matched_crop_name,
                        weather_risk_index=target_area.weather_risk_index,
                        origin_weather_risk_index=origin_area.weather_risk_index,
                        is_same_jma_area=(
                            origin_area.jma_area_code == target_area.jma_area_code
                        ),
                        relation_label=(
                            f"{origin_area.prefecture_name}→"
                            f"{target_area.prefecture_name}"
                        ),
                        reason=cls._build_sales_opportunity_reason(
                            origin_area, target_area, matched_crop_name
                        ),
                    )
                )

        sorted_candidates = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.weather_risk_index,
                not candidate.is_same_jma_area,
                candidate.origin_weather_risk_index,
                candidate.main_crop_name,
                candidate.origin_name,
            ),
        )

        selected_candidates = []
        selected_target_names = set()
        for candidate in sorted_candidates:
            if candidate.target_name in selected_target_names:
                continue
            selected_candidates.append(candidate)
            selected_target_names.add(candidate.target_name)
            if len(selected_candidates) == 5:
                break
        return selected_candidates

    @classmethod
    def _calculate_weather_risk_index(
        cls,
        weather_code: str,
        warning_city_count: int,
    ) -> float:
        """
        売り込み判断に使う天気リスク指数を算出します。

        天気コードの先頭2桁を主な判断軸とし、警報・注意報件数は
        小さな補正として倍率に近い数値へ畳み込みます。

        Args:
            weather_code: JMA天気コード。
            warning_city_count: 都道府県内の警報・注意報件数。

        Returns:
            float: 天気リスク指数。
        """
        weather_risk = cls._get_weather_base_risk(weather_code)
        warning_risk = min(0.8, warning_city_count * 0.15)
        return round(weather_risk + warning_risk, 1)

    @staticmethod
    def _get_weather_base_risk(weather_code: str) -> float:
        """
        JMA天気コード先頭2桁から天気由来の基礎リスクを返します。

        Args:
            weather_code: JMA天気コード。

        Returns:
            float: 晴れ、曇り、雨・雪、未取得を区別する基礎リスク。
        """
        if weather_code.startswith("3") or weather_code.startswith("4"):
            return 4.0

        weather_prefix = weather_code[:2]
        if weather_code in {"201", "210", "211"}:
            return 1.8
        if weather_prefix in {"14", "17", "18", "19", "21", "22"}:
            return 3.3
        if weather_prefix in {"12", "13", "15", "16", "20"}:
            return 2.6
        if weather_prefix == "11":
            return 1.6
        if weather_prefix == "10":
            return 1.1

        if weather_code.startswith("2"):
            return 2.6
        if weather_code.startswith("1"):
            return 1.1
        return 1.2

    @classmethod
    def _build_sales_opportunity_reason(
        cls,
        origin_area: PrefectureCommercialAreaVO,
        target_area: PrefectureCommercialAreaVO,
        crop_name: str,
    ) -> str:
        """
        売り込み候補の判断理由を画面表示用に組み立てます。

        Args:
            origin_area: 売り込み元商圏。
            target_area: 売り込み先商圏。
            crop_name: 売り込み元と売り込み先で一致した作物名。

        Returns:
            str: リスク指数に寄与した判断軸を含む説明文。
        """
        target_weather_summary = target_area.weather_name
        if target_area.warning_names:
            target_weather_summary = (
                f"{target_area.weather_name}、{target_area.warning_summary}"
            )
        return (
            f"{target_area.prefecture_name}は{target_weather_summary}で天気リスクが高い状態。"
            f"{origin_area.prefecture_name}は天気リスク指数が{origin_area.weather_risk_index}で、"
            f"同じ{crop_name}を出せるため、"
            f"{target_area.prefecture_name}への売り込み候補になります。"
        )
