from django.urls import path

from apps.medical.views import (
    AnalyzeDiagnosisAPIView,
    DiagnosisDetailAPIView,
    PatientDiagnosesListAPIView,
    PatientProblemsListAPIView,
    ProblemDetailAPIView,
)

app_name = "medical"

urlpatterns = [
    path(
        "diagnoses/analyze/",
        AnalyzeDiagnosisAPIView.as_view(),
        name="diagnoses-analyze",
    ),
    path(
        "patients/<int:patient_id>/problems/",
        PatientProblemsListAPIView.as_view(),
        name="patient-problems",
    ),
    path(
        "patients/<int:patient_id>/diagnoses/",
        PatientDiagnosesListAPIView.as_view(),
        name="patient-diagnoses",
    ),
    path("problems/<int:pk>/", ProblemDetailAPIView.as_view(), name="problem-detail"),
    path(
        "diagnoses/<int:pk>/",
        DiagnosisDetailAPIView.as_view(),
        name="diagnosis-detail",
    ),
]
