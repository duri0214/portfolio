"""HOME とカタログ詳細ページで共有するカタログの値を定義する。"""

from dataclasses import dataclass, replace

DEFAULT_THUMBNAIL = "no-image.png"


@dataclass(frozen=True)
class Catalog:
    """HOME に表示するアプリケーションのカタログ。

    Attributes:
        slug: カタログを識別するスラッグ。
        detail_path: 詳細画面のURLパス。
        detail_url_name: 詳細画面のURL名。
        app_url_name: アプリケーション画面のURL名。
        external_url: 外部アプリケーションのURL。
        app_label: Djangoアプリケーションラベル。
        thumbnail: サムネイルのファイル名。
        alt: サムネイル画像の代替テキスト。
        category: 表示するカテゴリ名。
        category_class: カテゴリ表示用のCSSクラス。
        title: カタログのタイトル。
        description: カタログの説明。
        detail_url: 解決済みの詳細画面URL。
        app_url: 解決済みのアプリケーションURL。
    """

    slug: str
    detail_path: str
    detail_url_name: str
    app_url_name: str | None
    external_url: str | None
    app_label: str
    thumbnail: str | None
    alt: str
    category: str
    category_class: str
    title: str
    description: str
    detail_url: str | None = None
    app_url: str | None = None

    @property
    def thumbnail_name(self) -> str:
        """表示するサムネイルのファイル名を返す。"""
        return self.thumbnail or DEFAULT_THUMBNAIL

    @property
    def thumbnail_path(self) -> str:
        """表示するサムネイルの静的ファイルパスを返す。"""
        return f"home/images/{self.thumbnail_name}"

    def with_urls(self, *, detail_url: str, app_url: str) -> "Catalog":
        """画面表示に必要なURLを設定した新しいカタログを返す。"""
        return replace(self, detail_url=detail_url, app_url=app_url)

    @classmethod
    def all(cls) -> tuple["Catalog", ...]:
        """登録済みのカタログを返す。"""
        return tuple(cls(**definition) for definition in _CATALOG_DEFINITIONS)

    @classmethod
    def get(cls, slug: str) -> "Catalog":
        """スラッグに対応するカタログを返す。"""
        return cls(**_CATALOG_DEFINITIONS_BY_SLUG[slug])


_CATALOG_DEFINITIONS = (
    {
        "slug": "hospital",
        "detail_path": "about/hospital/",
        "detail_url_name": "about_hospital",
        "app_url_name": "hsp:index",
        "external_url": None,
        "app_label": "HOSPITAL",
        "thumbnail": "hospital.png",
        "alt": "不在者投票転記ツール",
        "category": "病院",
        "category_class": "primary",
        "title": "不在者投票事務用の転記",
        "description": "2015年、友人の残業時間を減らすために開発。病棟別の不在者投票データを事務処理簿へ自動転記し、約6時間で完成。現場の作業時間削減と他病棟への展開につながった。現場で使える小さな自動化の効果を実感した最初の成果物。",
    },
    {
        "slug": "soil_analysis",
        "detail_path": "about/soil_analysis/",
        "detail_url_name": "about_soil_analysis",
        "app_url_name": "soil:home",
        "external_url": None,
        "app_label": "SOIL ANALYSIS",
        "thumbnail": "soil_analysis.png",
        "alt": "土壌分析レポートツール",
        "category": "農業",
        "category_class": "success",
        "title": "圃場計測のレポーティング",
        "description": "2023年、静岡で土壌分析に取り組み、圃場データの収集とレポート作成を支援。雨の日も風の日も計測し、現場でデータを集める難しさとIT活用の可能性を実感した。計測値を蓄積し、分析結果を共有する流れまでを見据えた。",
    },
    {
        "slug": "vietnam_research",
        "detail_path": "about/vietnam_research/",
        "detail_url_name": "about_vietnam_research",
        "app_url_name": "vnm:index",
        "external_url": None,
        "app_label": "VIETNAM",
        "thumbnail": "vietnam_research.png",
        "alt": "ベトナム株価分析ツール",
        "category": "経済",
        "category_class": "warning",
        "title": "ベトナムの株価を分析する",
        "description": "2019年、チャイナリスクを見据えた投資先としてベトナムを調査。名古屋市の経済交流ミッションにも参加し、現地訪問前のプレゼンテーション作成と株価分析に取り組んだ。調査結果を整理し、投資判断の材料を可視化することを目指した。",
    },
    {
        "slug": "gmarker",
        "detail_path": "about/gmarker/",
        "detail_url_name": "about_gmarker",
        "app_url_name": "mrk:index",
        "external_url": None,
        "app_label": "GMARKER",
        "thumbnail": "gmarker.png",
        "alt": "GoogleMapsピン配置ツール",
        "category": "地図",
        "category_class": "primary",
        "title": "GoogleMapsにピンをさす",
        "description": "2015年、飲食店などのキーワードでGoogle Mapsにピンをまとめて表示し、任意のピンだけに絞り込むツールを開発。初めて外部APIを使って作ったWebアプリ。地図上の大量の候補を整理し、必要な情報だけを見やすくすることを目指した。",
    },
    {
        "slug": "shopping",
        "detail_path": "about/shopping/",
        "detail_url_name": "about_shopping",
        "app_url_name": "shp:index",
        "external_url": None,
        "app_label": "SHOPPING",
        "thumbnail": "shopping.png",
        "alt": "ECサイト管理ツール",
        "category": "ＥＣ",
        "category_class": "success",
        "title": "通販サイトの基礎機能",
        "description": "2022年、ECサイト開発の基礎を身につけるために制作。店員・商品管理、CSV登録、写真アップロード、カード決済など、通販サイトに必要な一連の機能を実装した。管理画面から商品を登録し、購入までの流れを試せる構成にした。",
    },
    {
        "slug": "rental_shop",
        "detail_path": "about/rental_shop/",
        "detail_url_name": "about_rental_shop",
        "app_url_name": "ren:index",
        "external_url": None,
        "app_label": "RENTAL SHOP",
        "thumbnail": "rental_shop.png",
        "alt": "倉庫在庫管理ツール",
        "category": "倉庫",
        "category_class": "warning",
        "title": "倉庫のどこにいくつあるの？",
        "description": "2016年の物流オープンデータ活用コンテストをきっかけに構想。2023年、Webアプリ開発の経験を活かし、倉庫のどこに何がいくつあるかを検索できる形にした。商品名や保管場所から在庫を探し、現場の確認作業を減らすことを目指した。",
    },
    {
        "slug": "taxonomy",
        "detail_path": "about/taxonomy/",
        "detail_url_name": "about_taxonomy",
        "app_url_name": "txo:index",
        "external_url": None,
        "app_label": "TAXONOMY",
        "thumbnail": "taxonomy.png",
        "alt": "生物分類樹形図ツール",
        "category": "分類学",
        "category_class": "primary",
        "title": "ニワトリとミミズの種を分類",
        "description": "2017年、畑作業を通じて土壌の生物に興味を持ち、ニワトリやミミズの種類を登録して分類樹形図を作るアプリを開発。応用すれば家系図にも使える。生物の関係を視覚的にたどれるようにし、データ構造を画面で確認できるようにした。",
    },
    {
        "slug": "securities",
        "detail_path": "about/securities/",
        "detail_url_name": "about_securities",
        "app_url_name": "sec:index",
        "external_url": None,
        "app_label": "SECURITIES REPORT",
        "thumbnail": "securities.png",
        "alt": "有価証券報告書分析ツール",
        "category": "金融",
        "category_class": "success",
        "title": "金融庁の有価証券報告書を分析",
        "description": "2019年、有価証券報告書を取得・処理するプログラムを開発。2023年にはWebアプリへ移植し、企業情報の検索や財務データの分析まで行えるツールに発展させた。書類の収集から分析までをブラウザで行い、金融情報を扱う実用的な形に近づけた。",
    },
    {
        "slug": "llm_chat",
        "detail_path": "about/llm_chat/",
        "detail_url_name": "about_llm_chat",
        "app_url_name": "llm:index",
        "external_url": None,
        "app_label": "LLM CHAT",
        "thumbnail": "llm_chat.png",
        "alt": "LLM統合チャットツール",
        "category": "LLM",
        "category_class": "warning",
        "title": "GPTチャット",
        "description": "2024年、GeminiやChatGPTなど複数のLLM、画像生成、音声入出力、RAGを扱う仕組みを開発。共通ライブラリ化し、各アプリからLLMを利用できるようにした。モデルごとの違いを意識せず、アプリの機能としてAIを組み込める構成を目指した。",
    },
    {
        "slug": "ai_agent",
        "detail_path": "about/ai_agent/",
        "detail_url_name": "about_ai_agent",
        "app_url_name": "agt:index",
        "external_url": None,
        "app_label": "AI AGENT",
        "thumbnail": "ai_agent.png",
        "alt": "会話型AIエージェントシステム",
        "category": "LLM",
        "category_class": "primary",
        "title": "AI-AGENTの試作",
        "description": "2025年、複数のAIエージェントが役割分担して対話するシステムを構築。ターン制管理とガードレールで会話の流れと入力の安全性を制御し、専門的な応答を生成する。専門分野の異なるエージェントを組み合わせ、単独のチャットでは難しい応答を試した。",
    },
    {
        "slug": "jp_stocks",
        "detail_path": "about/jp_stocks/",
        "detail_url_name": "about_jp_stocks",
        "app_url_name": "jpn:index",
        "external_url": None,
        "app_label": "JP STOCKS",
        "thumbnail": "jp_stocks.png",
        "alt": "日本株分析ツール",
        "category": "経済",
        "category_class": "success",
        "title": "日本の株価を分析する",
        "description": "2025年、日本株の値動きを分析するアプリとして開発。現在は板情報の登録と売買シミュレーションを実装し、将来はRSSニュース取得などの機能追加を予定している。板情報を使った注文の流れを画面上で試せるため、株式売買の仕組みを学ぶ用途にも使える。",
    },
    {
        "slug": "welfare_services",
        "detail_path": "about/welfare_services/",
        "detail_url_name": "about_welfare_services",
        "app_url_name": "welf:index",
        "external_url": None,
        "app_label": "WELFARE SERVICES",
        "thumbnail": "welfare_services.png",
        "alt": "東京都福祉事務所情報ポータル",
        "category": "ハッカソン",
        "category_class": "info",
        "title": "東京都福祉事務所情報ポータル",
        "description": "2025年、東京都内の福祉事務所と障がい福祉サービスの空き情報を見える化。信号機表示で空き状況を直感的に把握できるポータルをハッカソンで開発した。利用者が地域やサービスを比較しやすくし、必要な支援へ早くたどり着けることを目指した。",
    },
    {
        "slug": "usa_research",
        "detail_path": "about/usa_research/",
        "detail_url_name": "about_usa_research",
        "app_url_name": "usa:index",
        "external_url": None,
        "app_label": "USA",
        "thumbnail": None,
        "alt": "USAニュース自動取得ツール",
        "category": "経済",
        "category_class": "primary",
        "title": "USAニュースを分析する",
        "description": "2025年、米国株や政治動向を追うため、主要ニュースサイトの記事タイトル・概要・公開日時を自動取得。経済、政策、テックなどの最新トレンドを短時間で確認できる。ニュースを収集・分類する作業を自動化し、日々の情報収集を効率化することを目指した。",
    },
    {
        "slug": "kokkai",
        "detail_path": "about/kokkai/",
        "detail_url_name": "about_kokkai",
        "app_url_name": "kokkai:index",
        "external_url": None,
        "app_label": "KOKKAI",
        "thumbnail": None,
        "alt": "国会議事録検索・分析システム",
        "category": "政治",
        "category_class": "info",
        "title": "国会議事録を分析する",
        "description": "2026年、国会議事録から必要な発言を検索し、AI（LLM）で要約・分析するシステムを開発。RAGで根拠となる議事録を参照し、質問への回答生成を目指す。膨大な一次資料を読み解く負担を減らし、根拠を確認しながら政策テーマを調べられるようにする。",
    },
    {
        "slug": "bank",
        "detail_path": "about/bank/",
        "detail_url_name": "about_bank",
        "app_url_name": "bank:index",
        "external_url": None,
        "app_label": "BANK",
        "thumbnail": None,
        "alt": "銀行CSV分析基盤",
        "category": "金融",
        "category_class": "info",
        "title": "銀行CSVを分析",
        "description": "2026年、銀行ごとに異なるCSV取引明細を取り込み、資金の流れを分析する基盤を開発。Rawデータを保持しながら、銀行横断のレポートを生成できる設計にした。取り込んだデータを分析し、日々の支出や資金の流れを把握しやすくすることを目指した。",
    },
    {
        "slug": "bookman",
        "detail_path": "about/bookman/",
        "detail_url_name": "about_bookman",
        "app_url_name": None,
        "external_url": "https://bookman.henojiya.net/",
        "app_label": "Bookman",
        "thumbnail": None,
        "alt": "図書館業務システム Bookman",
        "category": "図書館",
        "category_class": "info",
        "title": "図書館業務システム Bookman",
        "description": "支店ごとの蔵書管理、書籍CSV登録、貸出・返却、予約・取り置き、利用者管理を一つの画面で扱える図書館業務システム。蔵書の検索からカウンター業務までをまとめて管理し、現場の作業をシンプルにすることを目指した。",
    },
)

_CATALOG_DEFINITIONS_BY_SLUG = {
    definition["slug"]: definition for definition in _CATALOG_DEFINITIONS
}
