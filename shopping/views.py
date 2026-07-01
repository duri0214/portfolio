import logging
import os

from django.conf import settings
from django.contrib import messages
from django.utils.html import format_html
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

from .domain.repository.payment import StripePaymentRepository
from .domain.repository.product import ProductRepository
from .domain.repository.store_planning import (
    StorePlanningDataSourceRepository,
    StorePlanningTargetStoreRepository,
)
from .domain.repository.user_attribute import UserAttributeRepository
from .domain.service.csv_upload import CsvService
from .domain.service.payment import StripePaymentService
from .domain.service.store_planning_reviews import StorePlanningReviewService
from .domain.valueobject.store_planning import (
    AREA_HIERARCHY_LEVEL_PARENT_TOWN,
    StorePlanningArea,
    StorePlanningTargetLocation,
)
from .domain.valueobject.payment import PaymentIntent, PaymentInfo
from .forms import (
    ProductCreateFormSingle,
    ProductCreateFormBulk,
    ProductEditForm,
    StorePlanningTargetStoreCreateForm,
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
    """出店候補地を評判分析と周辺人口の両面から確認する画面。"""

    template_name = "shopping/store_planning.html"
    fallback_source_url = "https://www.e-stat.go.jp/stat-search/files?cycle=0&cycle_facet=tclass1%3Acycle&layout=datalist&page=1&tclass1=000001136472&tclass2=000001159886&tclass3val=0&toukei=00200521&tstat=000001136464"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        locations = StorePlanningTargetStoreRepository.get_active_locations()
        selected_location = self._selected_location()
        context["target_location"] = {
            "slug": selected_location.slug,
            "name": selected_location.name,
            "address": selected_location.address,
            "google_maps_url": selected_location.google_maps_url,
            "population_area": selected_location.population_area,
            "place_google_maps_embed_url": (
                selected_location.place_google_maps_embed_url
            ),
            "area_google_maps_embed_url": selected_location.area_google_maps_embed_url,
            "initial_map_embed_url": selected_location.area_google_maps_embed_url,
        }
        context["can_use_google_maps"] = (
            self.request.user.is_authenticated and self.request.user.is_superuser
        )
        context["store_locations"] = [
            {
                "slug": location.slug,
                "name": location.name,
                "address": location.address,
                "is_active": location.slug == selected_location.slug,
                "source_key": location.source_key,
            }
            for location in locations
        ]
        data_source_snapshot = (
            StorePlanningDataSourceRepository.get_latest_by_source_key(
                selected_location.source_key
            )
        )
        context["data_source_snapshots"] = [
            data_source_snapshot or self._fallback_data_source(selected_location)
        ]
        context["population_summary"] = self._build_population_summary(
            context["data_source_snapshots"]
        )
        context["population_age_rows"] = self._build_population_age_rows(
            context["data_source_snapshots"]
        )
        context["population_csv_coverage"] = (
            StorePlanningDataSourceRepository.get_population_csv_coverage()
        )
        region_level3_rows = self._build_region_level3_rows(selected_location)
        region_comparison_rows = self._build_region_comparison_rows(selected_location)
        context["region_level3_rows"] = region_level3_rows
        context["region_comparison_rows"] = region_comparison_rows
        context["region_table_rows"] = self._build_region_table_rows(
            region_level3_rows, region_comparison_rows
        )
        context["region_map_button_groups"] = self._build_region_map_button_groups(
            selected_location, region_level3_rows, region_comparison_rows
        )
        context["region_comparison_meta"] = self._build_region_comparison_meta(
            [*region_level3_rows, *region_comparison_rows]
        )
        context["has_fetched_data_sources"] = data_source_snapshot is not None
        context["review_summary"] = StorePlanningReviewService.build_summary(
            selected_location
        )
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") != "fetch_google_maps_reviews":
            return HttpResponseRedirect(reverse("shp:store_planning"))
        if not (request.user.is_authenticated and request.user.is_superuser):
            messages.warning(
                request,
                "Google Maps レビュー取得はスーパーユーザーでログインした場合のみ実行できます。",
            )
            return HttpResponseRedirect(reverse("shp:store_planning"))

        selected_location = self._selected_location()
        if selected_location.latitude is None or selected_location.longitude is None:
            messages.warning(
                request, "店舗候補の緯度経度がないためレビューを取得できません。"
            )
            return HttpResponseRedirect(
                self._store_planning_url(selected_location.slug)
            )

        api_key = os.getenv("GOOGLE_MAPS_BE_API_KEY")
        if not api_key:
            messages.warning(
                request,
                "レビュー取得の設定が未完了のため、今回は取得できませんでした。",
            )
            return HttpResponseRedirect(
                self._store_planning_url(selected_location.slug)
            )

        fetch_result = StorePlanningReviewService.fetch_reviews(
            api_key=api_key,
            target_location=selected_location,
        )
        if fetch_result.error_message:
            if fetch_result.error_url:
                messages.warning(
                    request,
                    format_html(
                        '{} <a href="{}" target="_blank" rel="noopener">{}</a>',
                        fetch_result.error_message,
                        fetch_result.error_url,
                        fetch_result.error_url_label or "確認する",
                    ),
                )
            else:
                messages.warning(request, fetch_result.error_message)
        elif fetch_result.skipped:
            messages.info(
                request,
                (
                    "Google Maps レビューは取得済みです。"
                    f"施設数: {fetch_result.place_count}件 / "
                    f"レビュー数: {fetch_result.review_count}件"
                ),
            )
        else:
            message = (
                f"取得施設数: {fetch_result.place_count}件 / "
                f"レビュー数: {fetch_result.review_count}件"
            )
            if fetch_result.review_count:
                messages.success(
                    request,
                    f"Google Maps レビュー取得を実行しました。{message}",
                )
            else:
                messages.warning(
                    request,
                    f"Google Maps レビュー取得を実行しましたが、レビューは見つかりませんでした。{message}",
                )
        return HttpResponseRedirect(self._store_planning_url(selected_location.slug))

    def _selected_location(self):
        requested_slug = self.request.GET.get("store")
        locations = StorePlanningTargetStoreRepository.get_active_locations()
        for location in locations:
            if location.slug == requested_slug:
                return location
        if locations:
            return locations[0]
        return StorePlanningTargetLocation(
            slug="chapter-table",
            name="Chapter Table",
            address="東京都足立区東保木間二丁目",
            latitude=35.792822,
            longitude=139.8143238,
            city_code="13121",
            town_code="073002",
            population_area="東京都足立区東保木間二丁目",
            large_area_name="東保木間",
            small_area_name="二丁目",
        )

    def _store_planning_url(self, store_slug: str) -> str:
        return f"{reverse('shp:store_planning')}?store={store_slug}"

    def _fallback_data_source(self, location):
        return {
            "display_name": f"e-Stat 国勢調査 年齢別人口: {location.name}",
            "source_url": self.fallback_source_url,
            "status": "データなし",
            "data_period": "データなし",
            "source_updated_at": None,
            "fetched_at": None,
            "raw_data": {
                "store_slug": location.slug,
                "store_name": location.name,
                "store_address": location.address,
                "target_area_name": location.population_area,
                "city_code": location.city_code,
                "town_code": location.town_code,
                "area_hierarchy_level": location.area_hierarchy_level,
                "age_groups": [],
            },
        }

    def _build_region_level3_rows(
        self, selected_location: StorePlanningTargetLocation
    ) -> list[dict]:
        snapshot = StorePlanningDataSourceRepository.get_parent_area_snapshot(
            selected_location.city_code, selected_location.town_code
        )
        if snapshot is None:
            return []
        area = self._area_from_snapshot(snapshot)
        return [self._build_region_comparison_row(area, selected_location)]

    def _build_region_comparison_rows(
        self,
        selected_location: StorePlanningTargetLocation,
    ) -> list[dict]:
        comparison_locations = self._comparison_locations(selected_location)
        return [
            self._build_region_comparison_row(location, selected_location)
            for location in comparison_locations
        ]

    def _comparison_locations(
        self,
        selected_location: StorePlanningTargetLocation,
    ) -> list[StorePlanningArea]:
        automatic_areas = self._automatic_comparison_areas(selected_location)
        if automatic_areas:
            has_selected_area = any(
                area.city_code == selected_location.city_code
                and area.town_code == selected_location.town_code
                for area in automatic_areas
            )
            if not has_selected_area:
                return [selected_location, *automatic_areas]
            return automatic_areas
        return [selected_location]

    def _build_region_table_rows(
        self, region_level3_rows: list[dict], region_comparison_rows: list[dict]
    ) -> list[dict]:
        wide_area_rows = [
            {**row, "area_level_label": "広域", "area_level_badge": "地域階層レベル3"}
            for row in region_level3_rows
        ]
        town_area_rows = [
            {**row, "area_level_label": "町丁", "area_level_badge": "地域階層レベル4"}
            for row in region_comparison_rows
        ]
        return [*wide_area_rows, *town_area_rows]

    def _automatic_comparison_areas(
        self, selected_location: StorePlanningTargetLocation
    ) -> list[StorePlanningArea]:
        """
        選択中の店舗地域を起点に、e-Stat CSVから町丁レベルの比較候補を取得する。

        町丁字コードは保存値を変更せず、Repositoryで検索に使う時だけ
        先頭ゼロを除いた先頭2桁相当の範囲にそろえる。これにより、
        店舗が属する町丁を基準に、同じ市区町村・地域階層レベル4の
        周辺候補を画面表示用の Value Object に変換する。
        """
        if not selected_location.town_code:
            return []
        snapshots = (
            StorePlanningDataSourceRepository.find_nearby_area_candidate_snapshots(
                city_code=selected_location.city_code,
                town_code=selected_location.town_code,
            )
        )
        return [
            self._area_from_snapshot(snapshot, selected_location=selected_location)
            for snapshot in snapshots
        ]

    def _area_from_snapshot(
        self,
        snapshot,
        selected_location: StorePlanningTargetLocation | None = None,
    ) -> StorePlanningArea:
        raw_data = snapshot.raw_data
        area_name = raw_data.get("target_area_name", snapshot.display_name)
        town_code = raw_data.get("town_code", "")
        is_selected_area = (
            selected_location is not None
            and raw_data.get("city_code") == selected_location.city_code
            and town_code == selected_location.town_code
        )
        return StorePlanningArea(
            slug=(
                selected_location.slug
                if is_selected_area
                else f"area-{raw_data.get('city_code', '')}-{town_code}"
            ),
            name=(
                selected_location.name
                if is_selected_area
                else f"自動候補（{raw_data.get('small_area_name') or area_name}）"
            ),
            address=selected_location.address if is_selected_area else area_name,
            latitude=selected_location.latitude if is_selected_area else None,
            longitude=selected_location.longitude if is_selected_area else None,
            city_code=raw_data.get("city_code", ""),
            town_code=town_code,
            population_area=area_name,
            large_area_name=raw_data.get("large_area_name", ""),
            small_area_name=raw_data.get("small_area_name", ""),
            area_hierarchy_level=raw_data.get("area_hierarchy_level", ""),
            comparison_note=self._comparison_note(raw_data),
        )

    def _comparison_note(self, raw_data: dict) -> str:
        if raw_data.get("area_hierarchy_level") == AREA_HIERARCHY_LEVEL_PARENT_TOWN:
            return "大字・町名単位の広域表示（地域階層レベル3）"
        return (
            "市区町村コード・地域階層レベル4・町丁字コード先頭2桁から抽出"
            "（境界未確認）"
        )

    def _build_region_comparison_row(
        self,
        location: StorePlanningArea,
        selected_location: StorePlanningTargetLocation,
    ) -> dict:
        data_source = StorePlanningDataSourceRepository.get_latest_by_source_key(
            location.source_key
        )
        source = data_source or self._fallback_data_source(location)
        population_summary = self._build_population_summary([source])
        return {
            "slug": location.slug,
            "name": location.name,
            "address": location.address,
            "population_area": location.population_area,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "google_maps_url": location.google_maps_url,
            "area_google_maps_url": location.area_google_maps_url,
            "area_google_maps_embed_url": location.area_google_maps_embed_url,
            "area_hierarchy_level": location.area_hierarchy_level,
            "comparison_note": location.comparison_note,
            "is_selected": location.slug == selected_location.slug,
            "population_summary": population_summary,
            "has_fetched_data_source": data_source is not None,
        }

    def _build_region_map_button_groups(
        self,
        selected_location: StorePlanningTargetLocation,
        region_level3_rows: list[dict],
        region_comparison_rows: list[dict],
    ) -> list[dict]:
        return [
            {
                "title": "広域（地域階層レベル3）",
                "description": "大字・町名単位の広域を俯瞰する。",
                "buttons": self._map_buttons_from_rows(region_level3_rows),
            },
            {
                "title": "町丁（地域階層レベル4）",
                "description": "町丁目単位の比較候補へ地図を移動する。",
                "buttons": self._map_buttons_from_rows(region_comparison_rows),
            },
        ]

    def _map_buttons_from_rows(self, rows: list[dict]) -> list[dict]:
        return [
            {
                "label": row["population_area"],
                "map_url": row["area_google_maps_embed_url"],
                "map_title": f"{row['population_area']} の地図",
                "is_selected": row["is_selected"],
            }
            for row in rows
        ]

    def _build_region_comparison_meta(self, rows: list[dict]) -> dict:
        for row in rows:
            summary = row.get("population_summary") or {}
            if summary:
                return {
                    "city_code": summary.get("city_code"),
                    "data_period": summary.get("data_period"),
                    "source_url": summary.get("stat_inf_url")
                    or summary.get("source_url"),
                    "source_updated_at": summary.get("source_updated_at"),
                    "last_modified_date": summary.get("last_modified_date"),
                }
        return {}

    def _build_population_summary(self, sources):
        for source in sources:
            raw_data = self._source_value(source, "raw_data", {})
            if raw_data.get("target_area_name"):
                return {
                    "target_area_name": raw_data.get("target_area_name"),
                    "store_name": raw_data.get("store_name"),
                    "store_address": raw_data.get("store_address"),
                    "total_population": raw_data.get("total_population"),
                    "stat_inf_id": raw_data.get("stat_inf_id"),
                    "resource_id": raw_data.get("resource_id"),
                    "table_name": raw_data.get("table_name"),
                    "city_code": raw_data.get("city_code"),
                    "town_code": raw_data.get("town_code"),
                    "release_date": raw_data.get("release_date"),
                    "last_modified_date": raw_data.get("last_modified_date"),
                    "average_age": raw_data.get("average_age"),
                    "male_population": raw_data.get("male_population"),
                    "female_population": raw_data.get("female_population"),
                    "source_updated_at": self._source_value(
                        source, "source_updated_at"
                    ),
                    "source_url": self._source_value(source, "source_url"),
                    "stat_inf_url": self._stat_inf_url(raw_data.get("stat_inf_id")),
                    "status": self._source_value(source, "status"),
                    "data_period": self._source_value(source, "data_period"),
                }
        return {}

    def _build_population_age_rows(self, sources):
        for source in sources:
            raw_data = self._source_value(source, "raw_data", {})
            if raw_data.get("age_groups"):
                max_population = max(
                    row["population"] or 0 for row in raw_data["age_groups"]
                )
                rows = []
                for row in raw_data["age_groups"]:
                    population_share = 0
                    if max_population and row.get("population") is not None:
                        population_share = round(
                            row["population"] / max_population * 100, 1
                        )
                    male_share, female_share = self._gender_share_pair(
                        row.get("male_population"), row.get("female_population")
                    )
                    rows.append(
                        {
                            **row,
                            "population_share": population_share,
                            "male_share": male_share,
                            "female_share": female_share,
                        }
                    )
                return rows
        return []

    def _gender_share_pair(self, male_population, female_population) -> tuple:
        male = male_population or 0
        female = female_population or 0
        total = male + female
        if not total:
            return 0, 0
        male_share = round(male / total * 100, 1)
        female_share = round(100 - male_share, 1)
        return male_share, female_share

    def _source_value(self, source, name: str, default=None):
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    def _stat_inf_url(self, stat_inf_id: str | None) -> str:
        if not stat_inf_id:
            return ""
        return f"https://www.e-stat.go.jp/stat-search/files?stat_infid={stat_inf_id}"


class StorePlanningTargetStoreCreateView(CreateView):
    """出店計画で選択するサンプル店舗候補を登録する。"""

    template_name = "shopping/store_planning_target_store/create.html"
    form_class = StorePlanningTargetStoreCreateForm

    def form_valid(self, form):
        messages.success(self.request, "出店計画のサンプル店舗を登録しました。")
        return super().form_valid(form)

    def get_success_url(self):
        return f"{reverse('shp:store_planning')}?store={self.object.slug}"


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
