from collections import Counter, defaultdict

from soil_analysis.domain.valueobject.market import (
    CommercialAreaVO,
    DispatchCandidateVO,
    NationalMarketVO,
)
from soil_analysis.models import JmaPrefecture, JmaWarning, Land, LandLedger


PREFECTURE_JAPAN_MAP_CODES = {
    "北海道": 1,
    "青森県": 2,
    "岩手県": 3,
    "宮城県": 4,
    "秋田県": 5,
    "山形県": 6,
    "福島県": 7,
    "茨城県": 8,
    "栃木県": 9,
    "群馬県": 10,
    "埼玉県": 11,
    "千葉県": 12,
    "東京都": 13,
    "神奈川県": 14,
    "新潟県": 15,
    "富山県": 16,
    "石川県": 17,
    "福井県": 18,
    "山梨県": 19,
    "長野県": 20,
    "岐阜県": 21,
    "静岡県": 22,
    "愛知県": 23,
    "三重県": 24,
    "滋賀県": 25,
    "京都府": 26,
    "大阪府": 27,
    "兵庫県": 28,
    "奈良県": 29,
    "和歌山県": 30,
    "鳥取県": 31,
    "島根県": 32,
    "岡山県": 33,
    "広島県": 34,
    "山口県": 35,
    "徳島県": 36,
    "香川県": 37,
    "愛媛県": 38,
    "高知県": 39,
    "福岡県": 40,
    "佐賀県": 41,
    "長崎県": 42,
    "熊本県": 43,
    "大分県": 44,
    "宮崎県": 45,
    "鹿児島県": 46,
    "沖縄県": 47,
}


class NationalMarketService:
    """
    既存の土壌分析データから全国商圏ダッシュボード用のVOを生成します。

    このServiceは、Djangoモデルに保存されている圃場・作付台帳・気象警報を
    トップページで扱いやすい読み取り専用の商圏情報へ変換する境界です。
    `Land` は `JmaCity -> JmaRegion -> JmaPrefecture` の関連をたどって
    都道府県単位の商圏へアサインし、画面では日本地図ライブラリと集計表に
    同じVOを渡します。

    DBモデルやマイグレーションは追加せず、既存データを集計して表示する
    PoC用途のServiceです。後続で市場価格、GraphRAG、物流APIなどを接続する
    場合も、画面側は `NationalMarketVO` を読むだけで済むようにします。
    """

    @classmethod
    def build(cls) -> NationalMarketVO:
        """
        全国商圏ダッシュボード全体の表示モデルを組み立てます。

        47都道府県のJMA都道府県マスタを基準に商圏を作るため、圃場が未登録の
        都道府県も `CommercialAreaVO` として返します。これにより、画面では
        「未登録」「稼働」「注意」の状態を日本地図ライブラリ上で欠けなく
        表現できます。

        Returns:
            NationalMarketVO: 都道府県別商圏と配車候補を束ねた表示用VO。
        """
        prefectures = list(JmaPrefecture.objects.all().order_by("code", "id"))
        land_stats = cls._build_land_stats()
        crop_stats = cls._build_crop_stats()
        warning_stats = cls._build_warning_stats()

        areas = [
            cls._build_area(prefecture, land_stats, crop_stats, warning_stats)
            for prefecture in prefectures
        ]
        dispatch_candidates = cls._build_dispatch_candidates(areas)
        return NationalMarketVO(areas=areas, dispatch_candidates=dispatch_candidates)

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
            prefecture_id = land.jma_city.jma_region.jma_prefecture_id
            stats[prefecture_id]["land_count"] += 1
            stats[prefecture_id]["company_ids"].add(land.company_id)
            stats[prefecture_id]["total_area"] += land.area or 0.0
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
            prefecture_id = ledger.land.jma_city.jma_region.jma_prefecture_id
            stats[prefecture_id][ledger.crop.name] += 1
        return stats

    @staticmethod
    def _build_warning_stats() -> Counter:
        """
        気象警報・注意報を都道府県別のリスク情報として集計します。

        商圏マップでは警報がある都道府県を「注意」として表示するため、
        `JmaWarning` をJMAリージョン経由で都道府県へ寄せます。件数は
        厳密な警報種別ではなく、地図上で注意喚起するための簡易リスク指標です。

        Returns:
            Counter: JMA都道府県IDごとの警報・注意報件数。
        """
        warning_stats = Counter()
        warnings = JmaWarning.objects.select_related("jma_region__jma_prefecture")
        for warning in warnings:
            prefecture_id = warning.jma_region.jma_prefecture_id
            warning_stats[prefecture_id] += 1
        return warning_stats

    @classmethod
    def _build_area(
        cls,
        prefecture: JmaPrefecture,
        land_stats: dict[int, dict],
        crop_stats: dict[int, Counter],
        warning_stats: Counter,
    ) -> CommercialAreaVO:
        """
        1都道府県分の集計値を商圏VOへ変換します。

        `CommercialAreaVO` はテンプレートでそのまま利用する表示用の値を持つため、
        ここで日本地図ライブラリ用の都道府県コード、状態判定に使うリスクスコア、
        主要作物名までまとめて確定させます。

        Args:
            prefecture: 商圏の基準となるJMA都道府県マスタ。
            land_stats: 都道府県別の圃場集計。
            crop_stats: 都道府県別の作物集計。
            warning_stats: 都道府県別の警報・注意報件数。

        Returns:
            CommercialAreaVO: トップページへ渡す1都道府県分の商圏VO。
        """
        stats = land_stats[prefecture.id]
        warning_city_count = warning_stats[prefecture.id]
        land_count = stats["land_count"]
        risk_score = cls._calculate_risk_score(land_count, warning_city_count)
        main_crop_name = cls._get_main_crop_name(crop_stats[prefecture.id])

        return CommercialAreaVO(
            prefecture_id=prefecture.id,
            prefecture_name=prefecture.name,
            japan_map_code=PREFECTURE_JAPAN_MAP_CODES[prefecture.name],
            land_count=land_count,
            company_count=len(stats["company_ids"]),
            main_crop_name=main_crop_name,
            total_area=round(stats["total_area"], 2),
            warning_city_count=warning_city_count,
            risk_score=risk_score,
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
        areas: list[CommercialAreaVO],
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
