from django.conf import settings
from django.db import models


class Patient(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Problem(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="problems",
    )
    title = models.CharField(max_length=255)
    summary = models.TextField()
    body_area = models.CharField(max_length=255, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    embedding_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Diagnosis(models.Model):
    class Kind(models.TextChoices):
        RADIOLOGY = "radiology", "Radiology"
        BLOOD_TEST = "blood_test", "Blood test"
        PHYSICAL_EXAM = "physical_exam", "Physical exam"
        DOCTOR_DIAGNOSIS = "doctor_diagnosis", "Doctor diagnosis"
        USER_NOTE = "user_note", "User note"
        OTHER = "other", "Other"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="diagnoses",
    )
    kind = models.CharField(max_length=64, choices=Kind.choices)
    title = models.CharField(max_length=255)
    raw_text = models.TextField(blank=True)
    raw_json = models.JSONField(default=dict, blank=True)
    raw_file = models.FileField(upload_to="diagnoses/", null=True, blank=True)
    happened_at = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    extracted_findings = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    body_areas = models.JSONField(default=list, blank=True)
    embedding_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class DiagnosisProblemLink(models.Model):
    class Strength(models.TextChoices):
        WEAK = "weak", "Weak"
        MODERATE = "moderate", "Moderate"
        STRONG = "strong", "Strong"

    diagnosis = models.ForeignKey(
        Diagnosis,
        on_delete=models.CASCADE,
        related_name="problem_links",
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.CASCADE,
        related_name="diagnosis_links",
    )
    strength = models.CharField(
        max_length=32,
        choices=Strength.choices,
        default=Strength.MODERATE,
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["diagnosis", "problem"],
                name="unique_diagnosis_problem_link",
            )
        ]


class AIRun(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    diagnosis = models.ForeignKey(
        Diagnosis,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_runs",
    )
    task = models.CharField(max_length=100)
    input_context = models.JSONField(default=dict, blank=True)
    output_json = models.JSONField(default=dict, blank=True)
    prompt = models.TextField(blank=True)
    raw_response = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
