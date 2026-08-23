"""HOME画面とカタログ詳細画面のビューを定義する。"""

from django.urls import reverse
from django.views.generic import TemplateView

from home.domain.valueobject.catalog import Catalog


class CatalogContextMixin:
    """カタログをテンプレート表示用の値に変換する。"""

    def _catalog_for_display(self, catalog: Catalog) -> Catalog:
        """URLを解決したカタログを返す。"""
        app_url = (
            reverse(catalog.app_url_name)
            if catalog.app_url_name
            else catalog.external_url
        )
        return catalog.with_urls(
            detail_url=reverse(f"home:{catalog.detail_url_name}"),
            app_url=app_url,
        )


class IndexView(CatalogContextMixin, TemplateView):
    """全カタログを表示するHOME画面のビュー。"""

    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        """全カタログを含むテンプレートコンテキストを返す。"""
        context = super().get_context_data(**kwargs)
        context["catalogs"] = [
            self._catalog_for_display(catalog) for catalog in Catalog.all()
        ]
        return context


class CatalogDetailView(CatalogContextMixin, TemplateView):
    """指定したカタログの詳細画面を表示するビュー。

    Attributes:
        catalog_slug: 表示対象のカタログを識別するスラッグ。
    """

    catalog_slug = None

    def get_context_data(self, **kwargs):
        """対象カタログを含むテンプレートコンテキストを返す。"""
        context = super().get_context_data(**kwargs)
        context["catalog"] = self._catalog_for_display(Catalog.get(self.catalog_slug))
        return context
