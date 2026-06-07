from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.medical.models import Diagnosis, Patient, Problem
from apps.medical.serializers import (
    DiagnosisAnalyzeInputSerializer,
    DiagnosisProblemLinkSerializer,
    DiagnosisSerializer,
    ProblemSerializer,
)
from apps.medical.services import DiagnosisAnalysisService


class AnalyzeDiagnosisAPIView(APIView):
    def post(self, request):
        serializer = DiagnosisAnalyzeInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = get_object_or_404(
            Patient,
            id=serializer.validated_data["patient_id"],
        )

        if patient.user != request.user and not request.user.is_staff:
            raise PermissionDenied("You cannot analyze diagnoses for this patient.")

        diagnosis = DiagnosisAnalysisService().analyze_and_save(
            patient_id=serializer.validated_data["patient_id"],
            kind=serializer.validated_data["kind"],
            title=serializer.validated_data["title"],
            raw_text=serializer.validated_data.get("raw_text", ""),
            raw_json=serializer.validated_data.get("raw_json", {}),
            happened_at=serializer.validated_data.get("happened_at"),
        )

        links = diagnosis.problem_links.select_related("problem").all()

        return Response(
            {
                "diagnosis": DiagnosisSerializer(diagnosis).data,
                "problem_links": DiagnosisProblemLinkSerializer(links, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class PatientProblemsListAPIView(generics.ListAPIView):
    serializer_class = ProblemSerializer

    def get_queryset(self):
        patient = get_object_or_404(Patient, id=self.kwargs["patient_id"])
        if patient.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You cannot view problems for this patient.")
        return patient.problems.order_by("-updated_at")


class PatientDiagnosesListAPIView(generics.ListAPIView):
    serializer_class = DiagnosisSerializer

    def get_queryset(self):
        patient = get_object_or_404(Patient, id=self.kwargs["patient_id"])
        if patient.user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You cannot view diagnoses for this patient.")
        return patient.diagnoses.order_by("-happened_at", "-created_at")


class ProblemDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ProblemSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Problem.objects.all()
        return Problem.objects.filter(patient__user=self.request.user)


class DiagnosisDetailAPIView(generics.RetrieveAPIView):
    serializer_class = DiagnosisSerializer

    def get_queryset(self):
        if self.request.user.is_staff:
            return Diagnosis.objects.all()
        return Diagnosis.objects.filter(patient__user=self.request.user)
