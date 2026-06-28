import logging

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    DetailView,
    CreateView,
    FormView,
    UpdateView,
    ListView,
    TemplateView,
)

from config import settings
from .domain.repository.payment import StripePaymentRepository
from .domain.repository.product import ProductRepository
from .domain.repository.user_attribute import UserAttributeRepository
from .domain.service.csv_upload import CsvService
from .domain.service.location_risk import LocationRiskService
from .domain.service.payment import StripePaymentService
from .domain.valueobject.payment import PaymentIntent, PaymentInfo
from .forms import (
    ProductCreateFormSingle,
    ProductCreateFormBulk,
    ProductEditForm,
    StaffEditForm,
    StaffDetailForm,
    StaffCreateForm,
    PurchaseForm,
)
from .models import Product, UserAttribute, BuyingHistory

# ロガーの取得
logger = logging.getLogger(__name__)


class CreateSingleView(CreateView):
    """単一商品登録"""

    model = Product
    template_name = "shopping/product/create_single.html"
    form_class = ProductCreateFormSingle

    def form_valid(self, form):
        try:
            self.object = form.save()
            return super().form_valid(form)
        except Exception as e:
            print(f"商品作成中にエラーが発生: {e}")
            form.add_error(None, f"商品の作成に失敗しました: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.warning(self.request, "フォームの入力に不備があります。")
        return super().form_invalid(form)

    def get_success_url(self):
        """作成した商品の詳細ページにリダイレクトする"""
        return reverse_lazy("shp:product_detail", kwargs={"pk": self.object.pk})


class CreateBulkView(FormView):
    template_name = "shopping/product/create_bulk.html"
    form_class = ProductCreateFormBulk
    success_url = reverse_lazy("shp:index")

    def form_valid(self, form):
        try:
            # CSVファイルをサービスに渡して処理
            csv_file = form.cleaned_data["file"]
            results = CsvService.process(csv_file)

            # 処理結果をメッセージとして表示
            if results["success_count"] > 0:
                detail_msg = []
                if results.get("created_count", 0) > 0:
                    detail_msg.append(f"新規登録: {results['created_count']}件")
                if results.get("updated_count", 0) > 0:
                    detail_msg.append(f"更新: {results['updated_count']}件")

                detail_text = f" ({', '.join(detail_msg)})" if detail_msg else ""
                messages.success(
                    self.request,
                    f"{results['success_count']}件の商品を正常に処理しました。{detail_text}",
                )

            if results["error_count"] > 0:
                messages.warning(
                    self.request,
                    f"{results['error_count']}件の商品で処理エラーが発生しました。",
                )
                for error in results["errors"][:5]:  # 最初の5つのエラーのみ表示
                    messages.error(self.request, error)
                if len(results["errors"]) > 5:
                    messages.error(
                        self.request,
                        f"他にも{len(results['errors']) - 5}件のエラーが発生しています。",
                    )

            return super().form_valid(form)

        except Exception as e:
            form.add_error(None, f"商品の一括作成に失敗しました: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "フォームの入力に問題があります")
        return super().form_invalid(form)


class IndexView(ListView):
    model = Product
    template_name = "shopping/index.html"
    paginate_by = 5

    def get_queryset(self):
        return ProductRepository.get_all_products()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["staffs"] = UserAttributeRepository.get_all_staff()
        context["customers"] = UserAttributeRepository.get_all_customers()
        return context


class StorePlanningView(TemplateView):
    """出店候補地を評判分析と立地リスクの両面から確認する画面。"""

    template_name = "shopping/store_planning.html"
    store_latitude = 35.79285640333462
    store_longitude = 139.81430669359216

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_location"] = {
            "name": "Chapter Table",
            "latitude": self.store_latitude,
            "longitude": self.store_longitude,
            "comparison_area": "北千住駅周辺",
            "google_maps_url": self._google_maps_url(
                self.store_latitude, self.store_longitude
            ),
        }
        context["location_assessment"] = LocationRiskService.assess(
            pedestrian_count_per_hour=30
        )
        context["data_sources"] = [
            {
                "name": "店前通行量の実測",
                "usage": "平日/休日、朝/昼/夕方に10分から15分だけ数えて1時間換算する",
                "status": "未取得: 実測が必要",
                "source_url": "",
            },
            {
                "name": "jSTAT MAP / 国勢調査",
                "usage": "半径500m圏の夜間人口、世帯属性、年代構成を確認する",
                "status": "取得元確定: 数値未取得",
                "source_url": "https://www.e-stat.go.jp/gis/gislp/",
            },
            {
                "name": "警視庁 交通量統計表",
                "usage": "近傍の主要交差点/主要断面に観測点があるか確認し、駅前側と比較する",
                "status": "取得元確定: 近傍観測点の確認が必要",
                "source_url": "https://catalog.data.metro.tokyo.lg.jp/dataset/t000022d0000000035",
            },
            {
                "name": "警察庁 交通事故統計オープンデータ",
                "usage": "事故地点を半径500mで抽出し、歩行者・自転車の安全面を補助指標にする",
                "status": "取得元確定: 抽出未実装",
                "source_url": "https://www.npa.go.jp/publications/statistics/koutsuu/opendata/index_opendata.html",
            },
        ]
        context["planning_axes"] = [
            {
                "title": "評判・口コミ",
                "summary": "Google Maps レビューを集約し、エリアの印象やネガティブ要因を把握する",
                "issue": "#131",
            },
            {
                "title": "通行量・周辺人口",
                "summary": "店前を通る人数と周辺人口から、通りすがり集客への依存度を判断する",
                "issue": "#803",
            },
        ]
        return context

    def _google_maps_url(self, latitude: float, longitude: float) -> str:
        return f"https://www.google.com/maps?q={latitude},{longitude}"


class ProductDetailView(DetailView):
    """
    商品詳細表示と購入数量入力を行うビュー
    TODO: 関連商品の表示機能を追加する
      - Product モデルに category フィールド（ForeignKey）を追加
      - または product_tags のような中間テーブルを作成して商品タグ付け
      - get_context_data メソッド内で同カテゴリ/タグの商品を取得
      - テンプレートに関連商品セクションを追加（カルーセル等）
      - レコメンデーションロジックを実装（閲覧履歴ベース、購入履歴ベースなど）
    TODO: 在庫管理機能を追加する
      - Product モデルに stock フィールドを追加
      - 購入時に在庫数をチェックして、不足している場合はエラーメッセージを表示
      - 購入完了時に在庫数を減らす処理を実装
    """

    template_name = "shopping/product/detail.html"
    model = Product

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.payment_repository = StripePaymentRepository()
        self.purchase_form = PurchaseForm()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["purchase_form"] = self.purchase_form
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = PurchaseForm(request.POST)

        if form.is_valid():
            return self._process_valid_form(form.cleaned_data["quantity"])
        else:
            messages.error(request, "入力内容に誤りがあります")
            context = self.get_context_data(object=self.object, purchase_form=form)
            return self.render_to_response(context)

    def _process_valid_form(self, quantity: int):
        """フォームのバリデーション後の処理"""
        user_id = self.request.user.id
        product_id = self.object.id

        try:
            # 支払い金額の計算
            payment_amounts = self.payment_repository.calculate_payment_amounts(
                product_id=product_id, quantity=quantity
            )

            # PaymentInfo値オブジェクトを作成
            payment_info = PaymentInfo(
                product_id=product_id,
                user_id=user_id,
                quantity=quantity,
                price=payment_amounts["price"],
                subtotal=payment_amounts["subtotal"],
                tax_amount=payment_amounts["tax_amount"],
                total_amount=payment_amounts["total_amount"],
                tax_rate=payment_amounts["tax_rate"],
            )

            # セッションに支払い情報を保存
            self.request.session["payment_info"] = payment_info.to_dict()

            # 確認画面にリダイレクト
            return HttpResponseRedirect(
                reverse("shp:payment_confirm", kwargs={"pk": product_id})
            )

        except ValueError as e:
            messages.error(self.request, str(e))
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)


class PaymentConfirmView(DetailView):
    model = Product
    template_name = "shopping/product/payment/confirm.html"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.payment_repository = StripePaymentRepository()
        self.payment_service = StripePaymentService()

    def get_context_data(self, **kwargs):
        """
        コンテキストデータを取得し、Stripe決済に必要な情報を追加します。

        public_key: StripeのAPIパブリックキー。テンプレート内でStripe Elementsを
        初期化する際に必要です。

        client_secret: PaymentIntentのクライアントシークレット。フロントエンドで
        決済を確認するために必要です。

        また、商品の価格計算や数量、税金などの決済に必要な情報も
        コンテキストに含めています。

        Returns:
            dict: 拡張されたコンテキストデータ
        """
        context = super().get_context_data(**kwargs)

        # セッションから支払い情報を取得
        payment_info_dict = self.request.session.get("payment_info")

        if payment_info_dict:
            payment_info = PaymentInfo.from_dict(payment_info_dict)

            # PaymentIntentを作成
            amount_in_int = int(payment_info.total_amount)
            payment_intent = PaymentIntent(
                amount=amount_in_int,
                currency="jpy",
                description=f"{self.object.name} × {payment_info.quantity}",
            )

            # PaymentIntentを作成してclient_secretを取得
            payment_result = self.payment_service.create_payment(payment_intent)

            if payment_result.success:
                context.update(
                    {
                        "quantity": payment_info.quantity,
                        "subtotal": payment_info.subtotal,
                        "tax": payment_info.tax_amount,
                        "total_price": payment_info.total_amount,
                        "public_key": settings.STRIPE_PUBLIC_KEY,
                        "client_secret": payment_result.client_secret,
                        "payment_intent_id": payment_result.payment_id,
                    }
                )
                # PaymentIntent IDをセッションに保存
                self.request.session["payment_intent_id"] = payment_result.payment_id
            else:
                context["error"] = (
                    f"決済の準備に失敗しました: {payment_result.error_message}"
                )
        else:
            context["error"] = "支払い情報が取得できませんでした。再度お試しください。"

        return context

    def post(self, request, *args, **kwargs):
        """
        Payment Intents APIによる決済完了後のPOSTリクエストを処理します。

        フロントエンドでの3DS認証完了後、PaymentIntentのステータスを確認し、
        購入履歴を作成して決済完了ページにリダイレクトします。

        Returns:
            HttpResponseRedirect: 決済完了ページへのリダイレクト
        """
        self.object = self.get_object()

        # セッションから支払い情報とPaymentIntent IDを取得
        payment_info_dict = request.session.get("payment_info")
        payment_intent_id = request.session.get("payment_intent_id")

        if not payment_info_dict or not payment_intent_id:
            messages.error(
                request,
                "支払い情報の取得に失敗しました。商品詳細ページからやり直してください。",
            )
            return HttpResponseRedirect(
                reverse("shp:product_detail", kwargs={"pk": self.object.pk})
            )

        payment_info = PaymentInfo.from_dict(payment_info_dict)

        try:
            # PaymentIntentのステータスを確認
            payment_result = self.payment_service.confirm_payment(payment_intent_id)

            if payment_result.success:
                logger.info(
                    f"支払い成功: ID={payment_intent_id}, 金額={payment_info.formatted_total_amount}円"
                )

                # 購入履歴の保存
                try:
                    history = BuyingHistory(
                        user=request.user,
                        product=self.object,
                        quantity=payment_info.quantity,
                        price=payment_info.price,  # 単価を保存
                        stripe_id=payment_intent_id,
                        payment_status=BuyingHistory.COMPLETED,
                    )
                    history.save()

                    # セッション削除
                    if "payment_info" in request.session:
                        del request.session["payment_info"]
                    if "payment_intent_id" in request.session:
                        del request.session["payment_intent_id"]

                    # 遷移先をshp:payment_completeに変更
                    return HttpResponseRedirect(
                        reverse("shp:payment_complete", kwargs={"pk": history.pk})
                    )
                except Exception as e:
                    logger.error(f"購入履歴保存エラー: {e}")
                    messages.error(
                        request, f"購入履歴の保存中にエラーが発生しました: {e}"
                    )
                    # エラー時は確認画面に戻る
                    context = self.get_context_data(object=self.object)
                    return self.render_to_response(context)
            else:
                logger.error(f"支払いエラー: {payment_result.error_message}")
                messages.error(
                    request, f"支払いに失敗しました: {payment_result.error_message}"
                )
                # エラー時は確認画面に戻る
                context = self.get_context_data(object=self.object)
                return self.render_to_response(context)
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            messages.error(request, f"予期しないエラーが発生しました: {e}")
            # エラー時は確認画面に戻る
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)


class PaymentCompleteView(DetailView):
    """支払い完了画面"""

    model = BuyingHistory
    template_name = "shopping/product/payment/complete.html"
    context_object_name = "buying_history"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 必要に応じて追加情報をコンテキストに入れる
        return context


class ProductEditView(UpdateView):
    template_name = "shopping/product/edit.html"
    form_class = ProductEditForm
    success_url = reverse_lazy("shp:index")
    model = Product


class StaffDetailView(DetailView):
    template_name = "shopping/staff/detail.html"
    form_class = StaffDetailForm
    model = UserAttribute


class StaffEditView(UpdateView):
    template_name = "shopping/staff/edit.html"
    form_class = StaffEditForm
    success_url = reverse_lazy("shp:index")
    model = UserAttribute


class StaffCreateView(CreateView):
    template_name = "shopping/staff/create.html"
    form_class = StaffCreateForm
    success_url = reverse_lazy("shp:index")
    model = UserAttribute
