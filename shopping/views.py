import logging

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    DetailView,
    CreateView,
    FormView,
    UpdateView,
    ListView,
)

from config import settings
from .domain.repository.payment import StripePaymentRepository
from .domain.repository.product import ProductRepository
from .domain.repository.staff import StaffRepository
from .domain.service.csv_upload import CsvService
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
from .models import Product, Staff, BuyingHistory

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
        print(form.errors)
        messages.add_message(self.request, messages.WARNING, form.errors)
        return redirect("shp:index")

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
        context["staffs"] = StaffRepository.get_all_staff()
        return context


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

        public_key: StripeのAPIパブリックキー。テンプレート内でStripeチェックアウトを
        初期化する際に必要です。これはStripeの決済フォームをクライアント側で
        レンダリングするために不可欠です。

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

            context.update(
                {
                    "quantity": payment_info.quantity,
                    "subtotal": payment_info.subtotal,
                    "tax": payment_info.tax_amount,
                    "total_price": payment_info.total_amount,
                    "public_key": settings.STRIPE_PUBLIC_KEY,
                }
            )
        else:
            context["error"] = "支払い情報が取得できませんでした。再度お試しください。"

        return context

    def post(self, request, *args, **kwargs):
        """
        Stripeからの決済完了後のPOSTリクエストを処理します。

        このメソッドは、Stripeチェックアウトフォームが送信された後に呼び出され、
        決済処理を行い、購入履歴を作成して決済完了ページにリダイレクトします。

        Returns:
            HttpResponseRedirect: 決済完了ページへのリダイレクト
        """
        self.object = self.get_object()

        # セッションから支払い情報を取得
        payment_info_dict = request.session.get("payment_info")

        if not payment_info_dict:
            messages.error(
                request,
                "支払い情報の取得に失敗しました。商品詳細ページからやり直してください。",
            )
            return HttpResponseRedirect(
                reverse("shp:product_detail", kwargs={"pk": self.object.pk})
            )
        payment_info = PaymentInfo.from_dict(payment_info_dict)

        try:
            # PaymentIntentオブジェクトの作成
            amount_in_int = int(payment_info.total_amount)
            payment_intent = PaymentIntent(
                amount=amount_in_int,  # Stripe APIは整数を受け取る
                currency="jpy",
                description=f"{self.object.name} × {payment_info.quantity}",  # 商品名と数量を説明文に付加
                payment_method=request.POST.get("stripeToken"),  # Stripeトークン
            )

            # 支払い処理の実行
            payment_result = self.payment_service.create_payment(payment_intent)

            if payment_result.success:
                logger.info(
                    f"支払い成功: ID={payment_result.payment_id}, 金額={payment_info.formatted_total_amount}円"
                )

                # 購入履歴の保存
                try:
                    history = BuyingHistory(
                        user=request.user,
                        product=self.object,
                        quantity=payment_info.quantity,
                        price=payment_info.price,  # 単価を保存
                        stripe_id=payment_result.payment_id,
                        payment_status=BuyingHistory.COMPLETED,
                    )
                    history.save()

                    # セッション削除
                    if "payment_info" in request.session:
                        del request.session["payment_info"]

                    # 遷移先をshp:payment_completeに変更
                    return HttpResponseRedirect(
                        reverse("shp:payment_complete", kwargs={"pk": history.pk})
                    )
                except Exception as e:
                    logger.error(f"購入履歴保存エラー: {e}")
                    messages.error(
                        request, f"購入履歴の保存中にエラーが発生しました: {e}"
                    )
            else:
                logger.error(f"支払いエラー: {payment_result.error_message}")
                messages.error(
                    request, f"支払いに失敗しました: {payment_result.error_message}"
                )
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            messages.error(request, f"予期しないエラーが発生しました: {e}")

        return HttpResponseRedirect(
            reverse("product_detail", kwargs={"pk": self.object.pk})
        )


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
    model = Staff


class StaffEditView(UpdateView):
    template_name = "shopping/staff/edit.html"
    form_class = StaffEditForm
    success_url = reverse_lazy("shp:index")
    model = Staff


class StaffCreateView(CreateView):
    template_name = "shopping/staff/create.html"
    form_class = StaffCreateForm
    success_url = reverse_lazy("shp:index")
    model = Staff
