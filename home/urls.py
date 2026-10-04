from django.urls import path

from home.domain.valueobject.catalog import Catalog
from home.views import CatalogDetailView, IndexView, send_apache_access_report

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path(
        "admin/apache-access-report/send/",
        send_apache_access_report,
        name="send_apache_access_report",
    ),
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
