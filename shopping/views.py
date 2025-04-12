from django.contrib import messages
from django.http import HttpResponseRedirect, HttpRequest, HttpResponse
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
from .domain.valueobject.payment import PaymentIntent
from .forms import (
    ProductCreateFormSingle,
    ProductCreateFormBulk,
    ProductEditForm,
    StaffEditForm,
    StaffDetailForm,
    StaffCreateForm,
    PurchaseForm,
)
from .models import Product, Staff, BuyingHistory  # TODO: repositoryに移動して


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

    # TODO: まだ見直し必要です

    def form_valid(self, form):
        try:
            # CSVファイルをサービスに渡して処理
            csv_file = form.cleaned_data["file"]
            results = CsvService.process(csv_file)

            # 処理結果をメッセージとして表示
            if results["success_count"] > 0:
                messages.success(
                    self.request,
                    f"{results['success_count']}件の商品を正常に処理しました。",
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
        self.purchase_form = None
        self.payment_repository = StripePaymentRepository()
        self.product_repository = ProductRepository()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # フォームをコンテキストに追加
        context["purchase_form"] = self.purchase_form
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = PurchaseForm(request.POST)
        self.purchase_form = form

        if form.is_valid():
            return self._process_valid_form(form)

        messages.error(request, "入力内容に問題があります。")
        return self.render_to_response(self.get_context_data())

    def _process_valid_form(self, form):
        """有効なフォームの処理"""
        product_id = self.object.id
        quantity = form.cleaned_data["quantity"]

        # 商品情報をリポジトリから取得
        product = self.payment_repository.get_product_by_id(product_id)
        if not product:
            messages.error(self.request, "商品が見つかりません。")
            return HttpResponseRedirect(self.request.path)

        # 在庫チェックは現段階では実装しない
        # 将来的にProduct モデルにstockフィールドを追加する予定

        # 購入確認画面へ進む
        if "confirm" in self.request.POST:
            return self._redirect_to_confirm(product_id, quantity)

        return self.render_to_response(self.get_context_data())

    @staticmethod
    def _redirect_to_confirm(pk, quantity):
        """購入確認画面へのリダイレクト"""
        url = reverse("shp:payment_confirm", kwargs={"pk": pk})
        return redirect(f"{url}?quantity={quantity}")


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
        quantity = int(self.request.GET.get("quantity", 1))
        product = self.get_object()

        # 必要な計算をビューで行う
        subtotal = product.price * quantity
        tax = subtotal * 0.1  # 消費税10%
        total_price = subtotal + tax

        context.update(
            {
                "quantity": quantity,
                "subtotal": subtotal,
                "tax": tax,
                "total_price": total_price,
                "public_key": settings.STRIPE_PUBLIC_KEY,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """
        Stripeからの決済完了後のPOSTリクエストを処理します。

        このメソッドは、Stripeチェックアウトフォームが送信された後に呼び出され、
        決済処理を行い、購入履歴を作成して決済完了ページにリダイレクトします。

        Returns:
            HttpResponseRedirect: 決済完了ページへのリダイレクト
        """
        product = self.get_object()
        quantity = int(request.GET.get("quantity", 1))
        total_amount = int(product.price * quantity * 1.1)  # 税込金額（10%）

        # Stripeトークンを取得
        token = request.POST.get("stripeToken")

        try:
            # PaymentIntentオブジェクトの作成
            payment_intent = PaymentIntent(
                amount=total_amount,
                currency="jpy",
                description=f"{product.name} × {quantity}個",
                payment_method=token,
            )

            # 支払い処理の実行
            payment_result = self.payment_service.create_payment(payment_intent)

            if payment_result.success:
                # 支払い成功時は購入履歴に記録
                saved = self.payment_repository.save_payment_record(
                    product_id=product.id,
                    user_id=request.user.id,
                    amount=total_amount,
                    payment_provider_id=payment_result.payment_id,
                )

                if saved:
                    # 決済完了ページにリダイレクト
                    return redirect("shp:payment_complete", pk=product.pk)
                else:
                    # 記録失敗時のエラーハンドリング
                    messages.error(
                        request,
                        "購入履歴の保存に失敗しました。サポートにお問い合わせください。",
                    )
                    return redirect("shp:payment_confirm", pk=product.pk)
            else:
                # 支払い失敗時のエラーメッセージ
                messages.error(request, f"決済エラー: {payment_result.error_message}")
                return redirect("shp:payment_confirm", pk=product.pk)

        except Exception as e:
            # 予期せぬエラーのハンドリング
            messages.error(request, f"予期せぬエラーが発生しました: {str(e)}")
            return redirect("shp:payment_confirm", pk=product.pk)


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
