from django.urls import include, path

from .views import (
    AnalyzeScanView,
    DashboardView,
    HealthCheckView,
    LaboratoryResultAttachmentDownloadView,
    LaboratoryResultCreateView,
    LoginView,
    LogoutView,
    MeView,
    OnboardingSyncView,
    SignupView,
)

app_name = "api"


def slash_compatible(route, view, *, name=None):
    route = route.rstrip("/")
    patterns = [path(f"{route}/", view, name=name)]

    if route:
        patterns.append(path(route, view))

    return patterns


urlpatterns = [
    *slash_compatible("health", HealthCheckView.as_view(), name="health-check"),
    *slash_compatible("auth/signup", SignupView.as_view(), name="signup"),
    *slash_compatible("auth/login", LoginView.as_view(), name="login"),
    *slash_compatible("auth/logout", LogoutView.as_view(), name="logout"),
    *slash_compatible("auth/me", MeView.as_view(), name="me"),
    *slash_compatible("dashboard", DashboardView.as_view(), name="dashboard"),
    *slash_compatible(
        "onboarding/sync",
        OnboardingSyncView.as_view(),
        name="onboarding-sync",
    ),
    *slash_compatible(
        "laboratory/results",
        LaboratoryResultCreateView.as_view(),
        name="laboratory-result-create",
    ),
    *slash_compatible(
        "analyze-scan",
        AnalyzeScanView.as_view(),
        name="analyze-scan",
    ),
    *slash_compatible(
        "analyze-scan/<str:scan_id>",
        AnalyzeScanView.as_view(),
        name="analyze-scan-by-id",
    ),
    *slash_compatible(
        "laboratory/results/attachments/<uuid:attachment_id>/download",
        LaboratoryResultAttachmentDownloadView.as_view(),
        name="laboratory-result-attachment-download",
    ),
    path("", include("apps.medical.urls")),
]
