import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers

from apps.core.models import LaboratoryResult, LaboratoryResultAttachment, PatientProfile
from apps.users.models import DoctorPatientAssignment, User


class LaboratoryResultInputSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    laboratory_request = serializers.CharField(max_length=128)
    laboratory_name = serializers.CharField(max_length=255)
    collected_at = serializers.DateTimeField()
    reported_at = serializers.DateTimeField()
    test_results = serializers.JSONField(required=False, default=list)

    def validate_test_results(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise serializers.ValidationError("Must be a valid JSON array.") from error
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a JSON array.")
        if any(not isinstance(item, dict) or not item.get("test_name") for item in value):
            raise serializers.ValidationError("Every structured result must be an object with test_name.")
        return value

    def validate(self, attrs):
        if attrs["reported_at"] < attrs["collected_at"]:
            raise serializers.ValidationError({"reported_at": "Cannot be before collected_at."})
        attrs["patient"] = self._patient_for_user(attrs.pop("patient_id"))
        return attrs

    def _patient_for_user(self, patient_id):
        user = self.context["request"].user
        patient = PatientProfile.objects.filter(pk=patient_id).select_related("user").first()
        if patient is None:
            raise serializers.ValidationError({"patient_id": "Patient not found."})
        if user.is_staff or user.role == User.Role.ADMIN:
            return patient
        if user.role == User.Role.PATIENT and patient.user_id == user.id:
            return patient
        if (
            user.role == User.Role.DOCTOR
            and hasattr(user, "doctor_profile")
            and DoctorPatientAssignment.objects.filter(
                doctor=user.doctor_profile,
                patient=patient,
            ).exists()
        ):
            return patient
        raise serializers.ValidationError(
            {"patient_id": "You do not have permission to add results for this patient."}
        )


class LaboratoryFileUploadSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

    def validate_user_id(self, value):
        try:
            user = User.objects.select_related("patient_profile", "doctor_profile").get(id=value)
        except User.DoesNotExist as error:
            raise serializers.ValidationError("Patient user not found.") from error

        if user.role != User.Role.PATIENT:
            raise serializers.ValidationError("The selected user is not a patient.")

        try:
            patient_profile = user.patient_profile
        except PatientProfile.DoesNotExist as error:
            raise serializers.ValidationError("The selected patient does not have a patient profile.") from error

        self.context["target_user"] = user
        self.context["target_patient_profile"] = patient_profile
        return value

    def validate(self, attrs):
        request = self.context["request"]
        target_user = self.context["target_user"]

        if request.user.id == target_user.id:
            return attrs

        requester_doctor = getattr(request.user, "doctor_profile", None)
        target_patient = self.context["target_patient_profile"]
        if (
            request.user.role == User.Role.DOCTOR
            and requester_doctor
            and DoctorPatientAssignment.objects.filter(
                doctor=requester_doctor,
                patient=target_patient,
            ).exists()
        ):
            return attrs

        raise serializers.ValidationError(
            {"user_id": "You can only upload files for yourself or for patients assigned to you."}
        )

    @property
    def target_patient_profile(self):
        return self.context["target_patient_profile"]


def attachment_type(upload):
    suffix = Path(upload.name).suffix.lower()
    if suffix == ".pdf":
        return LaboratoryResultAttachment.FileType.PDF
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return LaboratoryResultAttachment.FileType.IMAGE
    if suffix == ".dcm" and settings.LAB_RESULT_ALLOW_DICOM:
        return LaboratoryResultAttachment.FileType.DICOM
    allowed = "PDF, JPG, JPEG, PNG, and WEBP"
    if settings.LAB_RESULT_ALLOW_DICOM:
        allowed += ", and DCM"
    raise serializers.ValidationError(f"Unsupported attachment type. Allowed types: {allowed}.")


def validate_attachments(attachments):
    validated = []
    for upload in attachments:
        if upload.size > settings.LAB_RESULT_MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"{upload.name} exceeds the maximum file size of {settings.LAB_RESULT_MAX_FILE_SIZE} bytes."
            )
        validated.append((upload, attachment_type(upload)))
    return validated


def default_laboratory_result_payload(patient_profile):
    now = timezone.now()
    collected_at = now - timedelta(minutes=5)
    return {
        "laboratory_request": f"upload-{now.strftime('%Y%m%d%H%M%S')}",
        "laboratory_name": "VersaMed Upload Intake",
        "collected_at": collected_at,
        "reported_at": now,
        "test_results": [],
    }


@transaction.atomic
def create_laboratory_result(validated_data, attachments, user, patient=None):
    result = LaboratoryResult.objects.create(
        created_by=user,
        patient=patient,
        **validated_data,
    )
    for upload, file_type in attachments:
        LaboratoryResultAttachment.objects.create(
            laboratory_result=result,
            file=upload,
            file_type=file_type,
            title=Path(upload.name).name,
            uploaded_by=user,
        )
    return result


def laboratory_result_data(result):
    attachments = [
        {
            "id": str(attachment.id),
            "file_type": attachment.file_type,
            "title": attachment.title,
        }
        for attachment in result.attachments.all()
    ]
    value_count = len(result.test_results)
    attachment_count = len(attachments)
    return {
        "id": str(result.id),
        "patient_id": result.patient_id,
        "status": result.status,
        "patient_egn": result.patient.personal_identifier if result.patient else None,
        "summary": (
            f"{value_count} structured value{'s' if value_count != 1 else ''} and "
            f"{attachment_count} attachment{'s' if attachment_count != 1 else ''} uploaded."
        ),
        "test_results": result.test_results,
        "attachments": attachments,
    }
