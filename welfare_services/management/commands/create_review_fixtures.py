import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from welfare_services.models import Facility, FacilityReview

# 日本人の名前のサンプル
JAPANESE_NAMES = [
    "佐藤",
    "鈴木",
    "高橋",
    "田中",
    "伊藤",
    "渡辺",
    "山本",
    "中村",
    "小林",
    "加藤",
    "吉田",
    "山田",
    "佐々木",
    "山口",
    "松本",
    "井上",
    "木村",
    "林",
    "斎藤",
    "清水",
    "山崎",
    "中島",
    "池田",
    "阿部",
    "橋本",
    "山下",
    "森",
    "石川",
    "前田",
    "小川",
    "藤田",
    "岡田",
    "後藤",
    "長谷川",
    "石井",
    "村上",
    "近藤",
    "坂本",
    "遠藤",
    "青木",
]

# レビューコメントのサンプル
REVIEW_COMMENTS = [
    "スタッフの対応がとても丁寧で、安心して相談できました。",
    "必要な情報を的確に提供してくれて助かりました。",
    "待ち時間が長く、もう少し効率的な運営を期待します。",
    "施設内がきれいに整理されていて、利用しやすかったです。",
    "担当者の説明が分かりやすく、必要な手続きがスムーズに進みました。",
    "電話での対応が事務的で、もう少し親身になってほしいと感じました。",
    "子どもに対する配慮があり、安心して利用できる環境でした。",
    "手続きが複雑で、もう少し簡略化してほしいです。",
    "予約システムが便利で、待ち時間なく相談できました。",
    "福祉サービスについての豊富な知識があり、有益なアドバイスをもらえました。",
    "施設へのアクセスが良く、利用しやすかったです。",
    "職員の方々の連携がとれており、スムーズに対応してもらえました。",
    "もう少し利用者の立場に立った対応をしてほしいと思いました。",
    "必要な支援を迅速に受けることができ、大変感謝しています。",
    "子どもの障害に対する理解があり、適切なサポートを提案してくれました。",
    "書類の記入が多く、手続きに時間がかかりました。",
    "定期的なフォローアップがあり、継続的な支援を感じられます。",
    "相談員の方の専門知識が豊富で、安心して相談できました。",
    "施設内のバリアフリー対応が充実していて、移動が楽でした。",
    "他の支援機関との連携がスムーズで、総合的なサポートを受けられました。",
]

# 民間事業所名のサンプル
PRIVATE_FACILITIES = [
    "ひまわり福祉センター",
    "あおぞら支援ハウス",
    "さくら介護施設",
    "こころの相談室",
    "みどり福祉サービス",
    "つばさリハビリセンター",
    "のぞみ福祉会",
    "やすらぎの家",
    "ふれあい支援センター",
    "たんぽぽ福祉施設",
    "はなみずき介護ステーション",
    "あさひデイサービス",
    "まつば福祉ホーム",
    "いろは支援センター",
    "にじいろケアハウス",
    "東京障害者支援プラザ",
    "発達サポートセンターすまいる",
    "肢体不自由児通所施設はばたき",
    "自閉症支援センターピース",
    "特別支援学校放課後等デイサービス",
    "視覚障害者支援センターあいず",
    "聴覚障害児通所支援施設エコー",
    "知的障害者グループホームさくら",
    "精神障害者地域活動支援センター",
    "重症心身障害児デイサービスゆめ",
    "医療的ケア児支援施設ほっぷ",
    "障害児放課後等デイサービスきらり",
    "児童発達支援センターすてっぷ",
    "特別支援教育相談室かがやき",
    "東京都発達障害者支援センター",
    "東京障害者支援プラザ",
    "発達サポートセンターすまいる",
    "肢体不自由児通所施設はばたき",
    "自閉症支援センターピース",
    "特別支援学校放課後等デイサービス",
    "視覚障害者支援センターあいず",
    "聴覚障害児通所支援施設エコー",
    "知的障害者グループホームさくら",
    "精神障害者地域活動支援センター",
    "重症心身障害児デイサービスゆめ",
    "医療的ケア児支援施設ほっぷ",
    "障害児放課後等デイサービスきらり",
    "児童発達支援センターすてっぷ",
    "特別支援教育相談室かがやき",
    "東京都発達障害者支援センター",
]


class Command(BaseCommand):
    """レビューデータを生成するコマンド

    このコマンドは、開発・テスト用のレビューダミーデータを生成します。
    各福祉事務所ごとに指定された件数のレビューデータを生成します。
    障害者手帳の種類に応じて適切な等級を設定し、提携事業所名も含めて生成します。
    これにより、障害のある利用者や保護者が参考にできる質の高いレビューデータになります。
    障害者手帳の種類に応じて適切な等級を設定し、提携事業所名も含めて生成します。
    これにより、障害のある利用者や保護者が参考にできる質の高いレビューデータになります。
    """

    help = "福祉事務所のレビューデータを生成します"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="各施設ごとに生成するレビュー数を指定します（デフォルト: 10件）",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="既存のレビューデータを削除してから生成します",
        )

    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        # 施設データの確認
        facilities = Facility.objects.all()
        facility_count = facilities.count()

        if facility_count == 0:
            raise CommandError(
                "福祉事務所のデータが存在しません。先に福祉事務所データを作成してください。"
            )

        total_reviews = facility_count * count
        self.stdout.write(
            f"{facility_count}施設それぞれに{count}件ずつ、合計{total_reviews}件のレビューデータを生成します..."
        )

        # 既存データの削除（オプション）
        if clear:
            self.stdout.write("既存のレビューデータを削除します...")
            FacilityReview.objects.all().delete()

        # 現在の日時を取得
        now = timezone.now()

        created_objects = []

        # 各施設ごとに処理
        for facility in facilities:
            # 各施設に対して指定された件数のレビューを生成
            for i in range(count):
                # 各レビューごとに個別のトランザクションを使用
                with transaction.atomic():

                    # レビュー情報を生成
                    reviewer_name = f"{random.choice(JAPANESE_NAMES)} {random.choice(['太郎', '花子', '次郎', '優子', '健太', '美香'])}"
                    rating = random.randint(1, 5)  # 1〜5の評価

                    # 評価が高いほど肯定的なコメント、低いほど否定的なコメントになるよう調整
                    if rating >= 4:
                        # 高評価のコメント
                        comment_candidates = [
                            c
                            for c in REVIEW_COMMENTS
                            if "不" not in c and "ほしい" not in c
                        ]
                    elif rating <= 2:
                        # 低評価のコメント
                        comment_candidates = [
                            c
                            for c in REVIEW_COMMENTS
                            if "不" in c or "ほしい" in c or "長く" in c
                        ]
                    else:
                        # 中評価のコメント
                        comment_candidates = REVIEW_COMMENTS

                    comment = random.choice(comment_candidates)

                    # 障害者手帳情報
                    certificate_type = random.choice(
                        ["physical", "intellectual", "mental", "other"]
                    )
                    # 手帳番号は施設ID、ループカウンタ、現在時刻を組み合わせてユニークにする
                    certificate_number = f"{facility.pk}-{i}-{now.timestamp():.0f}{random.choice(['A', 'B', 'C', ''])}"

                    # 手帳の種類に応じた等級を設定
                    if certificate_type == "physical":
                        # 身体障害者手帳：1〜6級
                        certificate_grade = f"{random.randint(1, 6)}級"
                    elif certificate_type == "intellectual":
                        # 療育手帳：A, B, C（自治体によって異なる）
                        certificate_grade = random.choice(["A", "B", "C"])
                    elif certificate_type == "mental":
                        # 精神障害者保健福祉手帳：1〜3級
                        certificate_grade = f"{random.randint(1, 3)}級"
                    else:
                        # その他：任意
                        certificate_grade = random.choice(["軽度", "中度", "重度"])

                    # 民間事業所名（70%の確率で設定）
                    affiliated_facility_name = (
                        random.choice(PRIVATE_FACILITIES)
                        if random.random() < 0.7
                        else None
                    )

                    # 作成日をランダムに設定（過去1年以内）
                    days_ago = random.randint(1, 365)
                    created_at = now - timedelta(days=days_ago)

                    # レビューの承認状態（80%の確率で承認済み）
                    is_approved = random.random() < 0.8

                    # レビューオブジェクトを作成
                    try:
                        obj = FacilityReview.objects.create(
                            facility=facility,
                            reviewer_name=reviewer_name,
                            certificate_type=certificate_type,
                            certificate_number=certificate_number,
                            certificate_grade=certificate_grade,
                            rating=rating,
                            comment=comment,
                            affiliated_facility_name=affiliated_facility_name,
                            created_at=created_at,
                            updated_at=created_at,
                            is_approved=is_approved,
                        )
                        created_objects.append(obj)
                    except Exception as e:
                        # 手帳番号の重複などでエラーが発生した場合はスキップ
                        self.stderr.write(
                            f"レビュー作成中にエラーが発生しました [{facility.name}, {certificate_type}, {certificate_number}]: {e}"
                        )
                        continue

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(created_objects)}件のレビューデータを生成しました。"
            )
        )
