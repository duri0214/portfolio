from django.urls import reverse
from django.views.generic import TemplateView

from home.catalogs import CATALOGS, get_catalog


def build_catalog_context(slug):
    """
    カタログ定義に表示用のサムネイルパスと各リンクを追加する。

    Args:
        slug: 表示対象のカタログを識別する slug。

    Returns:
        HOME と詳細ページのテンプレートが利用する表示用のカタログ情報。
    """
    catalog = get_catalog(slug)
    catalog["thumbnail_path"] = f"home/images/{catalog['thumbnail']}"
    catalog["detail_url"] = reverse(f"home:{catalog['detail_url_name']}")

    if catalog["app_url_name"]:
        catalog["app_url"] = reverse(catalog["app_url_name"])
    else:
        catalog["app_url"] = catalog["external_url"]

    return catalog


class IndexView(TemplateView):
    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        """全カタログの表示用定義を HOME のコンテキストへ渡す。"""
        context = super().get_context_data(**kwargs)
        context["catalogs"] = [
            build_catalog_context(catalog["slug"]) for catalog in CATALOGS
        ]
        return context


class CatalogDetailView(TemplateView):
    """
    カタログ定義に対応する詳細ページを表示する共通ビュー。

    Attributes:
        catalog_slug: 表示対象のカタログを識別する slug。
    """

    catalog_slug = None

    def get_context_data(self, **kwargs):
        """対象カタログの表示用定義を詳細ページのコンテキストへ渡す。"""
        context = super().get_context_data(**kwargs)
        context["catalog"] = build_catalog_context(self.catalog_slug)
        return context
