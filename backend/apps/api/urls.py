from django.urls import re_path

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
    re_path(r"^health/?$", HealthCheckView.as_view(), name="health-check"),
    re_path(r"^auth/signup/?$", SignupView.as_view(), name="signup"),
    re_path(r"^auth/login/?$", LoginView.as_view(), name="login"),
    re_path(r"^auth/logout/?$", LogoutView.as_view(), name="logout"),
    re_path(r"^auth/me/?$", MeView.as_view(), name="me"),
    re_path(r"^dashboard/?$", DashboardView.as_view(), name="dashboard"),
    re_path(r"^onboarding/sync/?$", OnboardingSyncView.as_view(), name="onboarding-sync"),
    re_path(r"^laboratory/results/?$", LaboratoryResultCreateView.as_view(), name="laboratory-result-create"),
    re_path(
        r"^laboratory/results/attachments/(?P<attachment_id>[0-9a-f-]+)/download/?$",
        LaboratoryResultAttachmentDownloadView.as_view(),
        name="laboratory-result-attachment-download",
    ),
]
