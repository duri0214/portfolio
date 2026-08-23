from django.urls import path

from home.domain.valueobject.catalog import Catalog
from home.views import CatalogDetailView, IndexView

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]

urlpatterns += [
    path(
        catalog.detail_path,
        CatalogDetailView.as_view(
            catalog_slug=catalog.slug,
            template_name=f"home/{catalog.slug}/index.html",
        ),
        name=catalog.detail_url_name,
    )
    for catalog in Catalog.all()
]
