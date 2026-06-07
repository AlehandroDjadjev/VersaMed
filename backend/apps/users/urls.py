from django.urls import re_path

from .views import (
    CurrentUserView,
    CsrfTokenView,
    DoctorPatientAssignmentView,
    DoctorSignUpView,
    LoginView,
    LogoutView,
    PatientSignUpView,
    VerifyLoginView,
)

app_name = "users"

urlpatterns = [
    re_path(r"^csrf/?$", CsrfTokenView.as_view(), name="csrf"),
    re_path(r"^signup/patient/?$", PatientSignUpView.as_view(), name="signup-patient"),
    re_path(r"^signup/doctor/?$", DoctorSignUpView.as_view(), name="signup-doctor"),
    re_path(r"^login/?$", LoginView.as_view(), name="login"),
    re_path(r"^login/verify/?$", VerifyLoginView.as_view(), name="login-verify"),
    re_path(r"^logout/?$", LogoutView.as_view(), name="logout"),
    re_path(r"^me/?$", CurrentUserView.as_view(), name="me"),
    re_path(
        r"^doctor/patients/?$",
        DoctorPatientAssignmentView.as_view(),
        name="doctor-patients",
    ),
]
