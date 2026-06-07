from django.contrib.auth import login, logout
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.laboratory import (
    create_laboratory_result,
    laboratory_result_data,
    validate_attachments,
)
from apps.core.models import PatientProfile
from apps.medical.models import Diagnosis
from apps.medical.serializers import DiagnosisSerializer, ProblemSerializer
from apps.medical.services import DiagnosisAnalysisService, ensure_medical_patient
from his_mock.client import MockHospitalAPIClient

from .login_verification import create_login_challenge
from .models import DoctorPatientAssignment, User
from .serializers import (
    DoctorPatientAssignmentSerializer,
    DoctorPatientLookupSerializer,
    DoctorPatientWorkspaceSubmissionSerializer,
    DoctorSignUpSerializer,
    LoginSerializer,
    LoginVerificationSerializer,
    PatientSignUpSerializer,
    UserSerializer,
)


class DoctorRequiredMixin:
    def ensure_doctor(self, request):
        if request.user.role != User.Role.DOCTOR or not getattr(
            request.user, "doctor_profile", None
        ):
            return Response(
                {"detail": "Doctor profile required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def get_assignment(self, request, assignment_id):
        return get_object_or_404(
            DoctorPatientAssignment.objects.select_related("patient__user", "doctor__user"),
            id=assignment_id,
            doctor=request.user.doctor_profile,
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class PatientSignUpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientSignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class DoctorSignUpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorSignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        challenge = create_login_challenge(user)
        response_data = {
            "challenge_id": challenge.challenge_id,
            "expires_in": challenge.expires_in,
            "email": serializer.validated_data["email"],
        }

        if challenge.dev_code:
            response_data["dev_code"] = challenge.dev_code

        return Response(response_data, status=status.HTTP_202_ACCEPTED)


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class VerifyLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response({"user": UserSerializer(user).data})


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"user": None})

        return Response({"user": UserSerializer(request.user).data})


class DoctorPatientAssignmentView(DoctorRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        assignments = DoctorPatientAssignment.objects.filter(
            doctor=request.user.doctor_profile
        ).select_related("patient__user")
        return Response(
            {
                "assignments": DoctorPatientAssignmentSerializer(
                    assignments,
                    many=True,
                ).data
            }
        )

    def post(self, request):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        serializer = DoctorPatientLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        assignment, created = DoctorPatientAssignment.objects.get_or_create(
            doctor=request.user.doctor_profile,
            patient=patient,
        )
        return Response(
            {
                "assignment": DoctorPatientAssignmentSerializer(assignment).data,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def patient_dashboard_data(user, profile):
    mock = MockHospitalAPIClient().fetch_patient(profile.personal_identifier) or {
        "immunizations": [],
        "hospitalizations": [],
        "epicrises": [],
    }
    hospitalizations = [
        {
            "department": item.department,
            "diagnosis_code": item.diagnosis_code,
            "diagnosis": item.diagnosis,
            "admission_date": item.admission_date,
            "discharge_date": item.discharge_date,
            "institution": item.medical_institution.name,
            "epicrisis": {
                "summary": item.epicrisis.summary,
                "recommendations": item.epicrisis.recommendations,
            }
            if hasattr(item, "epicrisis")
            else None,
        }
        for item in profile.hospitalizations.select_related(
            "medical_institution",
            "epicrisis",
        )
    ]
    return {
        "patient": {
            "full_name": user.get_full_name(),
            "birth_date": profile.birth_date,
            "gender": profile.gender,
            "blood_type": profile.blood_type,
            "address": profile.address,
            "egn": profile.personal_identifier,
        },
        "mock_hospital_api": {
            "status": "connected",
            "patient_found": bool(mock),
            "records_available": {
                "immunizations": len(mock["immunizations"]),
                "hospitalizations": len(mock["hospitalizations"]),
                "epicrises": len(mock["epicrises"]),
            },
        },
        "database": {
            "immunizations": [
                {
                    "vaccine_name": item.vaccine_name,
                    "dose_number": item.dose_number,
                    "date": item.immunization_date,
                    "institution": item.medical_institution.name,
                }
                for item in profile.immunizations.select_related("medical_institution")
            ],
            "hospitalizations": hospitalizations,
            "laboratory_results": [
                laboratory_result_data(result)
                for result in profile.laboratory_results.prefetch_related("attachments")
                .select_related("created_by")
                .order_by("-reported_at", "-created_at")
            ],
        },
    }


class DoctorPatientWorkspaceView(DoctorRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assignment_id):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        assignment = self.get_assignment(request, assignment_id)
        profile = assignment.patient
        medical_patient = ensure_medical_patient(profile.user)

        diagnoses = medical_patient.diagnoses.order_by("-happened_at", "-created_at")
        problems = medical_patient.problems.order_by("-updated_at")

        return Response(
            {
                "assignment": DoctorPatientAssignmentSerializer(assignment).data,
                "patient_dashboard": patient_dashboard_data(profile.user, profile),
                "medical_workspace": {
                    "patient_id": medical_patient.id,
                    "problems": ProblemSerializer(problems, many=True).data,
                    "diagnoses": DiagnosisSerializer(diagnoses, many=True).data,
                },
            }
        )


class DoctorPatientWorkspaceSubmissionView(DoctorRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, assignment_id):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        assignment = self.get_assignment(request, assignment_id)
        serializer = DoctorPatientWorkspaceSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploads = request.FILES.getlist("attachments[]") or request.FILES.getlist(
            "attachments"
        )
        attachments = validate_attachments(uploads)
        medical_patient = ensure_medical_patient(assignment.patient.user)

        with transaction.atomic():
            laboratory_result = create_laboratory_result(
                {
                    "laboratory_request": serializer.validated_data["laboratory_request"],
                    "laboratory_name": serializer.validated_data["laboratory_name"],
                    "collected_at": serializer.validated_data["collected_at"],
                    "reported_at": serializer.validated_data["reported_at"],
                    "test_results": serializer.validated_data["test_results"],
                },
                attachments,
                request.user,
                patient=assignment.patient,
            )
            diagnosis = DiagnosisAnalysisService().analyze_and_save(
                patient_id=medical_patient.id,
                kind=serializer.validated_data["diagnosis_kind"],
                title=serializer.validated_data["title"],
                raw_text=serializer.validated_data.get("raw_text", ""),
                raw_json={
                    "laboratory_result_id": str(laboratory_result.id),
                    "laboratory_request": serializer.validated_data["laboratory_request"],
                    "laboratory_name": serializer.validated_data["laboratory_name"],
                    "structured_results": serializer.validated_data["test_results"],
                    "attachments": laboratory_result_data(laboratory_result)["attachments"],
                    **serializer.validated_data.get("raw_json", {}),
                },
                happened_at=serializer.validated_data.get("happened_at"),
            )

        return Response(
            {
                "laboratory_result": laboratory_result_data(laboratory_result),
                "diagnosis": DiagnosisSerializer(diagnosis).data,
                "patient_dashboard": patient_dashboard_data(
                    assignment.patient.user,
                    assignment.patient,
                ),
                "medical_workspace": {
                    "patient_id": medical_patient.id,
                    "problems": ProblemSerializer(
                        medical_patient.problems.order_by("-updated_at"),
                        many=True,
                    ).data,
                    "diagnoses": DiagnosisSerializer(
                        medical_patient.diagnoses.order_by("-happened_at", "-created_at"),
                        many=True,
                    ).data,
                },
            },
            status=status.HTTP_201_CREATED,
        )
