from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class StorePlanningReview:
    """
    出店計画画面で表示する Google Maps レビュー。

    Attributes:
        place_name: レビュー対象の施設名。
        author: レビュー投稿者名。
        review_text: レビュー本文。
        publish_time: レビュー公開日時。
        rating: 施設の Google Maps rating。
        distance_meter: 対象店舗候補から施設までの距離。
    """

    place_name: str
    author: str
    review_text: str
    publish_time: datetime | None
    rating: float | None
    distance_meter: int


@dataclass(frozen=True)
class StorePlanningReviewCell:
    """
    3x3 グリッドの1マスに集約した Google Maps レビュー指標。

    Attributes:
        row: 北から数えた行番号。
        col: 西から数えた列番号。
        label: 画面表示用の方角ラベル。
        place_count: レビューを持つ施設数。
        review_count: レビュー件数。
        average_rating: 施設 rating の平均。
        positive_count: ポジティブ系キーワードが含まれるレビュー件数。
        negative_count: ネガティブ系キーワードが含まれるレビュー件数。
        score: ヒートマップの濃淡に使う0から100の簡易スコア。
        background_color: ヒートマップセルの背景色。
        text_color: ヒートマップセルの文字色。
        reviews: セル内の代表レビュー。
    """

    row: int
    col: int
    label: str
    place_count: int = 0
    review_count: int = 0
    average_rating: float | None = None
    positive_count: int = 0
    negative_count: int = 0
    score: int = 0
    background_color: str = "#f8f9fa"
    text_color: str = "#212529"
    reviews: list[StorePlanningReview] = field(default_factory=list)


@dataclass(frozen=True)
class StorePlanningReviewSummary:
    """
    対象店舗候補の周辺レビュー集約結果。

    Attributes:
        radius_meter: 対象店舗候補からレビュー対象施設を拾う半径。
        total_place_count: 半径内でレビューを持つ施設数。
        total_review_count: 半径内のレビュー件数。
        average_rating: 半径内の施設 rating 平均。
        positive_count: ポジティブ系キーワードが含まれるレビュー件数。
        negative_count: ネガティブ系キーワードが含まれるレビュー件数。
        cells: 3x3 グリッドの集約セル。
        latest_reviews: 画面に表示する代表レビュー。
    """

    radius_meter: int
    total_place_count: int
    total_review_count: int
    average_rating: float | None
    positive_count: int
    negative_count: int
    cells: list[StorePlanningReviewCell]
    latest_reviews: list[StorePlanningReview]


@dataclass(frozen=True)
class StorePlanningReviewFetchResult:
    """
    Google Maps レビュー取得結果。

    Attributes:
        place_count: Places API から取得した施設数。
        review_count: 保存対象になったレビュー件数。
        skipped: 取得済みレビューがあり、API取得を省略したかどうか。
        error_message: 取得処理で表示すべきエラーがあった場合のメッセージ。
        error_url: エラー解消に使う参照先URL。
        error_url_label: エラー参照先リンクの表示名。
    """

    place_count: int
    review_count: int
    skipped: bool = False
    error_message: str = ""
    error_url: str = ""
    error_url_label: str = ""
