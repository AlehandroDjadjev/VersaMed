from django.contrib.auth import authenticate, get_user_model
from django.http import FileResponse
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from apps.core.models import DoctorProfile, LaboratoryResultAttachment, PatientProfile
from apps.core.services import sync_user_from_mock_hospital
from his_mock.client import MockHospitalAPIClient
from .ai_vision_service import analyze_scan_with_ai
from .scan_service import ScanNotFoundError, get_scan, list_scans, scan_image_path
from .laboratory import (
    LaboratoryResultInputSerializer,
    create_laboratory_result,
    laboratory_result_data,
    validate_attachments,
)


def user_data(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "status": "ok",
                "service": "backend",
                "message": "VersaMed backend is ready.",
            }
        )


class SignupView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get("username", "").strip()
        email = request.data.get("email", "").strip()
        password = request.data.get("password", "")
        role = request.data.get("role", "patient")
        if not username or not email or len(password) < 8:
            return Response(
                {"error": "Username, email, and password of at least 8 characters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if role not in {"patient", "doctor"}:
            return Response({"error": "Role must be patient or doctor."}, status=400)
        try:
            user = get_user_model().objects.create_user(
                username=username,
                email=email,
                password=password,
                role=role,
            )
        except IntegrityError:
            return Response({"error": "Username already exists."}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": user_data(user)}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        login_id = request.data.get("username", "").strip()
        user_model = get_user_model()
        matched_user = user_model.objects.filter(
            Q(username__iexact=login_id)
            | Q(email__iexact=login_id)
            | Q(patient_profile__personal_identifier=login_id)
            | Q(doctor_profile__uin=login_id)
        ).first()
        user = authenticate(
            request,
            username=matched_user.username if matched_user else login_id,
            password=request.data.get("password", ""),
        )
        if not user:
            return Response({"error": "Invalid username or password."}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": user_data(user)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"status": "logged_out"})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": user_data(request.user)})


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "patient":
            return self.patient_dashboard(user)
        if user.role == "doctor":
            return doctor_dashboard(user)
        return Response({"user": user_data(user), "database": {"users": user.__class__.objects.count()}})

    @staticmethod
    def patient_dashboard(user):
        try:
            profile = user.patient_profile
        except PatientProfile.DoesNotExist:
            return Response({"error": "No hospital record is linked to this account."}, status=404)
        mock = MockHospitalAPIClient().fetch_patient(profile.personal_identifier)
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
                } if hasattr(item, "epicrisis") else None,
            }
            for item in profile.hospitalizations.select_related("medical_institution", "epicrisis")
        ]
        return Response({
            "user": user_data(user),
            "patient": {
                "full_name": user.get_full_name(),
                "birth_date": profile.birth_date,
                "gender": profile.gender,
                "blood_type": profile.blood_type,
                "address": profile.address,
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
            },
        })


class OnboardingSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        identifier = request.data.get("personal_identifier") or request.data.get("uin")
        if not identifier:
            return Response({"error": "personal_identifier or uin is required."}, status=400)
        try:
            sync_user_from_mock_hospital(request.user, identifier)
        except IntegrityError:
            return Response({"error": "This hospital identifier is already linked to another account."}, status=409)
        except ValueError as error:
            return Response({"error": str(error)}, status=404)
        return Response({"status": "synced", "user": user_data(request.user)})


class LaboratoryResultCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = LaboratoryResultInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploads = request.FILES.getlist("attachments[]") or request.FILES.getlist("attachments")
        attachments = validate_attachments(uploads)
        if not serializer.validated_data["test_results"] and not attachments:
            raise ValidationError(
                {"detail": "At least one structured test result or attachment is required."}
            )
        result = create_laboratory_result(serializer.validated_data, attachments, request.user)
        return Response(laboratory_result_data(result), status=status.HTTP_201_CREATED)


class LaboratoryResultAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attachment_id):
        attachments = LaboratoryResultAttachment.objects.all()
        if not request.user.is_staff:
            attachments = attachments.filter(laboratory_result__created_by=request.user)
        attachment = get_object_or_404(attachments, id=attachment_id)
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.title,
        )


def doctor_dashboard(user):
    try:
        profile = user.doctor_profile
    except DoctorProfile.DoesNotExist:
        return Response({"error": "No hospital record is linked to this account."}, status=404)
    patients = PatientProfile.objects.select_related("user").all()
    return Response({
        "user": user_data(user),
        "doctor": {
            "full_name": user.get_full_name(),
            "uin": profile.uin,
            "specialty": profile.specialty,
            "institution": profile.medical_institution.name,
        },
        "mock_hospital_api": {"status": "connected", "doctor_found": bool(MockHospitalAPIClient().fetch_doctor(profile.uin))},
        "database": {
            "synthetic_patients": [
                {
                    "full_name": patient.user.get_full_name(),
                    "birth_date": patient.birth_date,
                    "blood_type": patient.blood_type,
                    "hospitalizations": patient.hospitalizations.count(),
                }
                for patient in patients
            ]
        },
    })


class ScanListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(list_scans())


class ScanDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, scan_id):
        try:
            return Response(get_scan(scan_id))
        except ScanNotFoundError as error:
            return Response({"error": str(error)}, status=404)


class ScanImageView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, scan_id):
        try:
            scan = get_scan(scan_id)
            return FileResponse(scan_image_path(scan).open("rb"), content_type="image/png")
        except ScanNotFoundError as error:
            return Response({"error": str(error)}, status=404)
        except FileNotFoundError as error:
            return Response({"error": str(error)}, status=404)


class AnalyzeScanView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, scan_id):
        try:
            scan = get_scan(scan_id)
            result = analyze_scan_with_ai(scan)
        except ScanNotFoundError as error:
            return Response({"error": str(error)}, status=404)
        except FileNotFoundError as error:
            return Response({"error": str(error)}, status=503)
        except RuntimeError as error:
            return Response({"error": str(error)}, status=503)
        except Exception:
            return Response({"error": "AI scan analysis failed. Try again later."}, status=502)
        return Response({"scan": scan, "aiResult": result})
