from django.shortcuts import get_object_or_404
from rest_framework import generics, status
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
        return patient.problems.order_by("-updated_at")


class PatientDiagnosesListAPIView(generics.ListAPIView):
    serializer_class = DiagnosisSerializer

    def get_queryset(self):
        patient = get_object_or_404(Patient, id=self.kwargs["patient_id"])
        return patient.diagnoses.order_by("-happened_at", "-created_at")


class ProblemDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ProblemSerializer
    queryset = Problem.objects.all()


class DiagnosisDetailAPIView(generics.RetrieveAPIView):
    serializer_class = DiagnosisSerializer
    queryset = Diagnosis.objects.all()
