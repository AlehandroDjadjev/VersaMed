import json
from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from apps.core.models import LaboratoryResult, LaboratoryResultAttachment


class LaboratoryResultInputSerializer(serializers.Serializer):
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
        return attrs


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


@transaction.atomic
def create_laboratory_result(validated_data, attachments, user):
    result = LaboratoryResult.objects.create(created_by=user, **validated_data)
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
        "status": result.status,
        "summary": (
            f"{value_count} structured value{'s' if value_count != 1 else ''} and "
            f"{attachment_count} attachment{'s' if attachment_count != 1 else ''} uploaded."
        ),
        "test_results": result.test_results,
        "attachments": attachments,
    }
