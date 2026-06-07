import json
import logging
import time

from django.contrib.auth import authenticate, get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.db.models import Q
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.authtoken.models import Token
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import DoctorProfile, LaboratoryResultAttachment, PatientProfile
from apps.core.email_notifications import send_email_notification
from apps.core.services import sync_user_from_mock_hospital
from apps.medical.models import Diagnosis, Patient as MedicalPatient
from apps.medical.serializers import DiagnosisProblemLinkSerializer, DiagnosisSerializer
from apps.medical.services import DiagnosisAnalysisService
from his_mock.client import MockHospitalAPIClient
from .ai_vision_service import analyze_scan_with_ai
from .scan_service import ScanNotFoundError, get_scan, scan_image_path
from .laboratory import (
    LaboratoryFileUploadSerializer,
    LaboratoryResultInputSerializer,
    create_laboratory_result,
    default_laboratory_result_payload,
    laboratory_result_data,
    validate_attachments,
)
from .notifications import CanSendEmailNotification, EmailNotificationSerializer


logger = logging.getLogger(__name__)


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
        records_available = {
            "immunizations": len(mock["immunizations"]) if mock else 0,
            "hospitalizations": len(mock["hospitalizations"]) if mock else 0,
            "epicrises": len(mock["epicrises"]) if mock else 0,
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
                "records_available": records_available,
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
                    laboratory_result_data(item)
                    for item in profile.laboratory_results.prefetch_related("attachments")
                ],
            },
        })


class OnboardingSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        identifier = request.data.get("personal_identifier") or request.data.get("uin")
        if not identifier:
            return Response({"error": "personal_identifier or uin is required."}, status=400)
        previous_hospitalization_ids = self.get_existing_hospitalization_ids(request.user)

        try:
            profile = sync_user_from_mock_hospital(request.user, identifier)
        except IntegrityError:
            return Response({"error": "This hospital identifier is already linked to another account."}, status=409)
        except ValueError as error:
            return Response({"error": str(error)}, status=404)

        analyzed = []
        analysis_errors = []

        if request.user.role == "patient":
            candidate_hospitalizations = []
            hospitalizations = profile.hospitalizations.select_related(
                "medical_institution",
                "epicrisis",
            )

            for hospitalization in hospitalizations:
                is_new_source = hospitalization.his_document_id not in previous_hospitalization_ids
                if is_new_source or self.needs_his_analysis(request.user, hospitalization):
                    candidate_hospitalizations.append(hospitalization)

            for hospitalization in candidate_hospitalizations:
                try:
                    result = self.analyze_hospitalization(request.user, hospitalization)
                    if result:
                        analyzed.append(result)
                except Exception as error:
                    analysis_errors.append(
                        {
                            "source_id": hospitalization.his_document_id,
                            "message": str(error),
                        }
                    )

        new_problem = None
        for item in analyzed:
            if item["problem_links"]:
                new_problem = item["problem_links"][0]["problem"]
                break

        return Response(
            {
                "status": "synced",
                "user": user_data(request.user),
                "new_records": {
                    "hospitalizations": len(analyzed) + len(analysis_errors),
                },
                "analyzed_diagnoses": analyzed,
                "latest_diagnosis": self.get_latest_diagnosis(request.user),
                "analysis_errors": analysis_errors,
                "new_problem": new_problem,
            }
        )

    def get_existing_hospitalization_ids(self, user):
        if user.role != "patient":
            return set()

        try:
            profile = user.patient_profile
        except PatientProfile.DoesNotExist:
            return set()

        return set(profile.hospitalizations.values_list("his_document_id", flat=True))

    def needs_his_analysis(self, user, hospitalization):
        medical_patient = MedicalPatient.objects.filter(user=user).first()
        if not medical_patient:
            return True

        diagnosis = Diagnosis.objects.filter(
            patient=medical_patient,
            raw_json__source="his_hospitalization",
            raw_json__source_id=hospitalization.his_document_id,
        ).first()

        if not diagnosis:
            return True

        return not diagnosis.description and not diagnosis.problem_links.exists()

    def analyze_hospitalization(self, user, hospitalization):
        medical_patient, _ = MedicalPatient.objects.get_or_create(
            user=user,
            defaults={"name": user.get_full_name() or user.username},
        )

        existing_diagnosis = Diagnosis.objects.filter(
            patient=medical_patient,
            raw_json__source="his_hospitalization",
            raw_json__source_id=hospitalization.his_document_id,
        ).first()

        if existing_diagnosis:
            if existing_diagnosis.description or existing_diagnosis.problem_links.exists():
                return None

            existing_diagnosis.delete()

        raw_text = self.hospitalization_raw_text(hospitalization)
        diagnosis = DiagnosisAnalysisService().analyze_and_save(
            patient_id=medical_patient.id,
            kind=Diagnosis.Kind.DOCTOR_DIAGNOSIS,
            title=f"{hospitalization.diagnosis} ({hospitalization.diagnosis_code})",
            happened_at=hospitalization.admission_date,
            raw_text=raw_text,
            raw_json={
                "source": "his_hospitalization",
                "source_id": hospitalization.his_document_id,
                "diagnosis_code": hospitalization.diagnosis_code,
                "department": hospitalization.department,
                "institution": hospitalization.medical_institution.name,
                "admission_date": hospitalization.admission_date.isoformat(),
                "discharge_date": hospitalization.discharge_date.isoformat()
                if hospitalization.discharge_date
                else None,
            },
            include_enrichment=False,
        )
        links = diagnosis.problem_links.select_related("problem").all()

        return {
            "source_id": hospitalization.his_document_id,
            "diagnosis": DiagnosisSerializer(diagnosis).data,
            "problem_links": DiagnosisProblemLinkSerializer(links, many=True).data,
        }

    def get_latest_diagnosis(self, user):
        medical_patient = MedicalPatient.objects.filter(user=user).first()
        if not medical_patient:
            return None

        diagnosis = (
            medical_patient.diagnoses.order_by("-happened_at", "-created_at")
            .prefetch_related("problem_links__problem")
            .first()
        )
        if not diagnosis:
            return None

        links = diagnosis.problem_links.select_related("problem").all()
        return {
            "source_id": diagnosis.raw_json.get("source_id", "") if diagnosis.raw_json else "",
            "diagnosis": DiagnosisSerializer(diagnosis).data,
            "problem_links": DiagnosisProblemLinkSerializer(links, many=True).data,
        }

    def hospitalization_raw_text(self, hospitalization):
        lines = [
            f"HIS hospitalization document: {hospitalization.his_document_id}",
            f"Diagnosis: {hospitalization.diagnosis} ({hospitalization.diagnosis_code})",
            f"Department: {hospitalization.department}",
            f"Institution: {hospitalization.medical_institution.name}",
            f"Admission date: {hospitalization.admission_date}",
            f"Discharge date: {hospitalization.discharge_date or 'not recorded'}",
        ]

        if hasattr(hospitalization, "epicrisis"):
            lines.extend(
                [
                    f"Epicrisis summary: {hospitalization.epicrisis.summary}",
                    f"Recommendations: {hospitalization.epicrisis.recommendations}",
                ]
            )

        return "\n".join(lines)


class LaboratoryResultCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = LaboratoryFileUploadSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        uploads = (
            request.FILES.getlist("attachments[]")
            or request.FILES.getlist("attachments")
            or request.FILES.getlist("file")
        )
        attachments = validate_attachments(uploads)
        if not attachments:
            raise ValidationError({"file": "Upload at least one file."})
        result = create_laboratory_result(
            default_laboratory_result_payload(serializer.target_patient_profile),
            attachments,
            request.user,
            patient=serializer.target_patient_profile,
        )
        return Response(laboratory_result_data(result), status=status.HTTP_201_CREATED)


@method_decorator(xframe_options_sameorigin, name="dispatch")
class LaboratoryResultAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, attachment_id):
        attachments = LaboratoryResultAttachment.objects.all()
        if not request.user.is_staff:
            allowed = Q(laboratory_result__created_by=request.user) | Q(
                laboratory_result__patient__user=request.user
            )
            if request.user.role == "doctor" and hasattr(request.user, "doctor_profile"):
                allowed |= Q(
                    laboratory_result__patient__doctor_assignments__doctor=request.user.doctor_profile
                )
            attachments = attachments.filter(allowed).distinct()
        attachment = get_object_or_404(attachments, id=attachment_id)
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=request.query_params.get("preview") != "1",
            filename=attachment.title,
        )


class EmailNotificationCreateView(APIView):
    permission_classes = [IsAuthenticated, CanSendEmailNotification]

    def post(self, request):
        serializer = EmailNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = send_email_notification(
            user=request.user,
            **serializer.validated_data,
        )
        if not result["success"]:
            return Response(
                {"success": False, "message": "Failed to send email."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"success": True, "message": "Email sent successfully."})


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


class AnalyzeScanView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    class InputSerializer(serializers.Serializer):
        patient_id = serializers.IntegerField(required=False)
        title = serializers.CharField(max_length=255, required=False, allow_blank=True)
        modality = serializers.CharField(max_length=64, required=False, allow_blank=True)
        body_part = serializers.CharField(max_length=128, required=False, allow_blank=True)
        user_complaint = serializers.CharField(required=False, allow_blank=True)
        patient_symptoms = serializers.CharField(required=False, allow_blank=True)
        clinical_context = serializers.CharField(required=False, allow_blank=True)
        focus_hint = serializers.CharField(required=False, allow_blank=True)
        happened_at = serializers.DateField(required=False, allow_null=True)
        symptoms = serializers.CharField(required=False, allow_blank=True)
        image = serializers.FileField(required=False)

    def _resolve_patient(self, request, patient_id):
        if patient_id is not None:
            patient = get_object_or_404(MedicalPatient, id=patient_id)
            if patient.user != request.user and not request.user.is_staff:
                raise ValidationError({"patient_id": ["You cannot use this patient record."]})
            return patient
        if request.user.is_staff:
            raise ValidationError({"patient_id": ["patient_id is required for staff users."]})
        patient, _ = MedicalPatient.objects.get_or_create(
            user=request.user,
            defaults={"name": request.user.get_full_name() or request.user.username},
        )
        return patient

    def _parse_symptoms(self, raw_value):
        if not raw_value:
            return []
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in text.split(",") if item.strip()]

    def post(self, request, scan_id=None):
        request_started = time.perf_counter()
        logger.warning(
            "scan_pipeline.start user_id=%s scan_id=%s",
            getattr(request.user, "id", None),
            scan_id or "",
        )
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        logger.warning(
            "scan_pipeline.input_valid user_id=%s has_image=%s title=%s",
            getattr(request.user, "id", None),
            bool(payload.get("image")),
            payload.get("title", ""),
        )
        patient = self._resolve_patient(request, payload.get("patient_id"))
        logger.warning(
            "scan_pipeline.patient_resolved user_id=%s patient_id=%s",
            getattr(request.user, "id", None),
            patient.id,
        )
        image_upload = payload.get("image")
        patient_symptoms = payload.get("patient_symptoms", "").strip()

        if scan_id:
            try:
                scan = get_scan(scan_id)
                image_path = scan_image_path(scan)
            except ScanNotFoundError as error:
                return Response({"error": str(error)}, status=404)
            except FileNotFoundError as error:
                return Response({"error": str(error)}, status=404)
            image_upload = SimpleUploadedFile(
                image_path.name,
                image_path.read_bytes(),
                content_type="image/png",
            )
            if not patient_symptoms:
                raise ValidationError(
                    {"patient_symptoms": ["This field is required for scan-id analysis."]}
                )
        else:
            if not image_upload:
                raise ValidationError({"image": ["This field is required."]})
            if not payload.get("title"):
                raise ValidationError({"title": ["This field is required."]})
            if not patient_symptoms:
                patient_symptoms = (
                    payload.get("user_complaint", "").strip()
                    or ", ".join(self._parse_symptoms(payload.get("symptoms", "")))
                )
            scan = {
                "id": "",
                "title": payload["title"],
                "modality": payload.get("modality", ""),
                "bodyPart": payload.get("body_part", ""),
                "symptoms": self._parse_symptoms(payload.get("symptoms", "")),
                "symptomsSource": "uploaded_by_user",
                "userComplaint": payload.get("user_complaint", ""),
                "clinicalContext": payload.get("clinical_context", ""),
                "focusHint": payload.get("focus_hint", ""),
            }
        try:
            vision_started = time.perf_counter()
            logger.warning(
                "scan_pipeline.vision.start user_id=%s patient_id=%s",
                getattr(request.user, "id", None),
                patient.id,
            )
            result = analyze_scan_with_ai(
                scan,
                image_upload,
                patient_symptoms=patient_symptoms,
            )
            logger.warning(
                "scan_pipeline.vision.done user_id=%s patient_id=%s elapsed_ms=%d",
                getattr(request.user, "id", None),
                patient.id,
                int((time.perf_counter() - vision_started) * 1000),
            )
        except RuntimeError as error:
            logger.warning(
                "scan_pipeline.vision.runtime_error user_id=%s patient_id=%s error=%s",
                getattr(request.user, "id", None),
                patient.id,
                str(error),
            )
            return Response({"error": str(error)}, status=503)
        except Exception as exc:
            logger.exception(
                "scan_pipeline.vision.unhandled_error user_id=%s patient_id=%s error=%s",
                getattr(request.user, "id", None),
                patient.id,
                str(exc),
            )
            return Response({"error": "AI scan analysis failed. Try again later."}, status=502)
        diagnosis_raw_text = "\n".join(
            [
                f"Scan title: {scan['title']}",
                f"Modality: {scan['modality']}",
                f"Body part: {scan['bodyPart']}",
                f"Symptoms: {', '.join(scan.get('symptoms', [])) or 'not provided'}",
                f"User complaint: {scan.get('userComplaint', '')}",
                f"Clinical context: {scan.get('clinicalContext', '')}",
                "Preliminary scan analysis:",
                json.dumps(result, indent=2),
            ]
        )
        diagnosis_started = time.perf_counter()
        logger.warning(
            "scan_pipeline.diagnosis.start user_id=%s patient_id=%s",
            getattr(request.user, "id", None),
            patient.id,
        )
        diagnosis = DiagnosisAnalysisService().analyze_and_save(
            patient_id=patient.id,
            kind=Diagnosis.Kind.RADIOLOGY,
            title=f"{scan['title']} image analysis",
            raw_text=diagnosis_raw_text,
            raw_json={
                "source": "scan_image_analysis" if scan_id else "uploaded_scan_analysis",
                "scan_id": scan_id or "",
                "scan": scan,
                "scan_analysis": result,
            },
            happened_at=payload.get("happened_at"),
        )
        links = diagnosis.problem_links.select_related("problem").all()
        logger.warning(
            "scan_pipeline.done user_id=%s patient_id=%s diagnosis_id=%s links=%s diagnosis_ms=%d total_ms=%d",
            getattr(request.user, "id", None),
            patient.id,
            diagnosis.id,
            links.count(),
            int((time.perf_counter() - diagnosis_started) * 1000),
            int((time.perf_counter() - request_started) * 1000),
        )
        return Response(
            {
                "scan": scan,
                "aiResult": result,
                "diagnosis": DiagnosisSerializer(diagnosis).data,
                "problem_links": DiagnosisProblemLinkSerializer(links, many=True).data,
            }
        )
