import uuid

from django.db import models
from django.conf import settings

from .storage import PrivateMediaStorage


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MedicalInstitution(TimestampedModel):
    name = models.CharField(max_length=255)
    nhif_number = models.CharField(max_length=32, unique=True)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=32, blank=True)


class PatientProfile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile")
    personal_identifier = models.CharField(max_length=32, unique=True)
    birth_date = models.DateField()
    gender = models.CharField(max_length=16, blank=True)
    blood_type = models.CharField(max_length=8, blank=True)
    address = models.CharField(max_length=255, blank=True)


class DoctorProfile(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    uin = models.CharField(max_length=32, unique=True)
    specialty = models.CharField(max_length=128)
    medical_institution = models.ForeignKey(MedicalInstitution, on_delete=models.PROTECT, related_name="doctors")


class Immunization(TimestampedModel):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="immunizations")
    medical_institution = models.ForeignKey(MedicalInstitution, on_delete=models.PROTECT)
    his_document_id = models.CharField(max_length=64, unique=True)
    vaccine_name = models.CharField(max_length=128)
    lot_number = models.CharField(max_length=64)
    dose_number = models.PositiveSmallIntegerField()
    immunization_date = models.DateField()


class Hospitalization(TimestampedModel):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="hospitalizations")
    medical_institution = models.ForeignKey(MedicalInstitution, on_delete=models.PROTECT)
    his_document_id = models.CharField(max_length=64, unique=True)
    admission_date = models.DateField()
    discharge_date = models.DateField(null=True, blank=True)
    department = models.CharField(max_length=128)
    diagnosis_code = models.CharField(max_length=32)
    diagnosis = models.CharField(max_length=255)


class Epicrisis(TimestampedModel):
    hospitalization = models.OneToOneField(Hospitalization, on_delete=models.CASCADE, related_name="epicrisis")
    his_document_id = models.CharField(max_length=64, unique=True)
    summary = models.TextField()
    recommendations = models.TextField(blank=True)


class LaboratoryResult(TimestampedModel):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    laboratory_request = models.CharField(max_length=128)
    laboratory_name = models.CharField(max_length=255)
    collected_at = models.DateTimeField()
    reported_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    test_results = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="laboratory_results",
    )


class LaboratoryResultAttachment(models.Model):
    class FileType(models.TextChoices):
        PDF = "pdf", "PDF"
        IMAGE = "image", "Image"
        DICOM = "dicom", "DICOM"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    laboratory_result = models.ForeignKey(
        LaboratoryResult,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(storage=PrivateMediaStorage(), upload_to="laboratory_results/attachments/")
    file_type = models.CharField(max_length=16, choices=FileType.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="laboratory_result_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)


class EmailNotification(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="email_notifications",
        null=True,
        blank=True,
    )
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
