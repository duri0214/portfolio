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

from .domain.repository.payment import StripePaymentRepository
from .domain.service.csv_upload import CsvService
from .forms import (
    ProductCreateFormSingle,
    ProductCreateFormBulk,
    ProductEditForm,
    StaffEditForm,
    StaffDetailForm,
    StaffCreateForm,
    PurchaseForm,
)
from .models import Products, Staff


class CreateSingleView(CreateView):
    """単一商品登録"""

    model = Products
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
    model = Products
    template_name = "shopping/index.html"
    paginate_by = 5

    def get_queryset(self):
        return Products.objects.order_by("id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["staffs"] = Staff.objects.all()
        return context


class ProductDetailView(DetailView):
    """
    商品詳細表示と購入数量入力を行うビュー
    TODO: 関連商品の表示機能を追加する
      - Products モデルに category フィールド（ForeignKey）を追加
      - または products_tags のような中間テーブルを作成して商品タグ付け
      - get_context_data メソッド内で同カテゴリ/タグの商品を取得
      - テンプレートに関連商品セクションを追加（カルーセル等）
      - レコメンデーションロジックを実装（閲覧履歴ベース、購入履歴ベースなど）
    TODO: 在庫管理機能を追加する
      - Products モデルに stock フィールドを追加
      - 購入時に在庫数をチェックして、不足している場合はエラーメッセージを表示
      - 購入完了時に在庫数を減らす処理を実装
    """

    template_name = "shopping/product/detail.html"
    model = Products

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase_form = PurchaseForm()  # 初期値1のフォームを作成
        self.payment_repository = StripePaymentRepository()

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
        # 将来的にProducts モデルにstockフィールドを追加する予定

        # 購入確認画面へ進む
        if "confirm" in self.request.POST:
            return self._redirect_to_confirm(product_id, quantity)

        return self.render_to_response(self.get_context_data())

    @staticmethod
    def _redirect_to_confirm(product_id, quantity):
        """購入確認画面へのリダイレクト"""
        url = reverse("shp:payment_confirm", kwargs={"pk": product_id})
        return redirect(f"{url}?quantity={quantity}")


class ProductEditView(UpdateView):
    template_name = "shopping/product/edit.html"
    form_class = ProductEditForm
    success_url = reverse_lazy("shp:index")
    model = Products


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
