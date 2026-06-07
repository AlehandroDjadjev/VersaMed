from django.urls import path

from .views import (
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

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("onboarding/sync/", OnboardingSyncView.as_view(), name="onboarding-sync"),
    path("laboratory/results/", LaboratoryResultCreateView.as_view(), name="laboratory-result-create"),
    path(
        "laboratory/results/attachments/<uuid:attachment_id>/download/",
        LaboratoryResultAttachmentDownloadView.as_view(),
        name="laboratory-result-attachment-download",
    ),
]
