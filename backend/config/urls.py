from django.contrib import admin
from django.urls import include, path

from apps.core.views import EmptyHomeView

urlpatterns = [
    path("", EmptyHomeView.as_view(), name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("auth/", include("apps.users.urls")),
]
