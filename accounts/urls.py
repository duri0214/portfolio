from django.urls import path

from accounts.views import AccountActivationView, RegistrationView

app_name = "accounts"

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path(
        "activate/<uidb64>/<token>/", AccountActivationView.as_view(), name="activate"
    ),
]
