from django.urls import path

from .views import AnalyzeScanView, DashboardView, HealthCheckView, LoginView, LogoutView, MeView, OnboardingSyncView, ScanDetailView, ScanImageView, ScanListView, SignupView

app_name = "api"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("onboarding/sync/", OnboardingSyncView.as_view(), name="onboarding-sync"),
    path("scans", ScanListView.as_view(), name="scan-list"),
    path("scans/<str:scan_id>", ScanDetailView.as_view(), name="scan-detail"),
    path("scans/<str:scan_id>/image", ScanImageView.as_view(), name="scan-image"),
    path("analyze-scan/<str:scan_id>", AnalyzeScanView.as_view(), name="analyze-scan"),
]
