"""portfolio URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("home.urls")),
    path("vietnam_research/", include("vietnam_research.urls")),
    path("gmarker/", include("gmarker.urls")),
    path("shopping/", include("shopping.urls")),
    path("linebot_engine/", include("linebot_engine.urls")),
    path("warehouse/", include("warehouse.urls")),
    path("taxonomy/", include("taxonomy.urls")),
    path("soil_analysis/", include("soil_analysis.urls")),
    path("securities/", include("securities.urls")),
    path("hospital/", include("hospital.urls")),
    path("llm_chat/", include("llm_chat.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
