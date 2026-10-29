from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    # Serve the API-connected frontend from Django's own origin.
    path("app/", TemplateView.as_view(template_name="app.html"), name="frontend_app"),
    path("api-auth/", include("rest_framework.urls")),
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("portal.urls")),
]
