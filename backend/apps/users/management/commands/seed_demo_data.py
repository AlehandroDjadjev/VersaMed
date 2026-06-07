from datetime import date, timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError
from django.utils import timezone

from apps.core.models import (
    LaboratoryResult,
    LaboratoryResultAttachment,
    MedicalInstitution,
)
from apps.core.services import sync_user_from_mock_hospital
from apps.medical.models import AIRun, Diagnosis, DiagnosisProblemLink, Problem
from apps.medical.services import ensure_medical_patient
from apps.users.models import DoctorPatientAssignment


User = get_user_model()
DEMO_LAB_RESULT_ID = UUID("4f6b357a-5aaf-4f72-91ac-c30c8db0d001")


class Command(BaseCommand):
    help = "Create a hardcoded doctor and patient pair for manual UI testing."

    def handle(self, *args, **options):
        try:
            institution, _ = MedicalInstitution.objects.get_or_create(
                nhif_number="VM-DEMO-001",
                defaults={
                    "name": "VersaMed Demo Clinic",
                    "city": "Sofia",
                    "address": "12 Demo Health Avenue",
                    "phone_number": "+35920000999",
                },
            )
        except OperationalError as exc:
            raise CommandError(
                "Database tables are missing. Run `python manage.py migrate` first, then run `python manage.py seed_demo_data` again."
            ) from exc

        doctor_user, doctor_created = User.objects.get_or_create(
            username="doctor.elena",
            defaults={
                "email": "elena.georgieva@versamed.test",
                "first_name": "Elena",
                "middle_name": "Stoyanova",
                "last_name": "Georgieva",
                "role": User.Role.DOCTOR,
                "onboarding_completed": True,
            },
        )
        doctor_user.email = "elena.georgieva@versamed.test"
        doctor_user.first_name = "Elena"
        doctor_user.middle_name = "Stoyanova"
        doctor_user.last_name = "Georgieva"
        doctor_user.phone_number = "+359888100001"
        doctor_user.role = User.Role.DOCTOR
        doctor_user.onboarding_completed = True
        doctor_user.set_password("DemoDoctor123!")
        doctor_user.save()

        doctor_profile = sync_user_from_mock_hospital(doctor_user, "1234567890")

        patient_user, patient_created = User.objects.get_or_create(
            username="patient.ivan",
            defaults={
                "email": "ivan.ivanov@versamed.test",
                "first_name": "Ivan",
                "middle_name": "Petrov",
                "last_name": "Ivanov",
                "role": User.Role.PATIENT,
                "onboarding_completed": True,
            },
        )
        patient_user.email = "ivan.ivanov@versamed.test"
        patient_user.first_name = "Ivan"
        patient_user.middle_name = "Petrov"
        patient_user.last_name = "Ivanov"
        patient_user.phone_number = "+359888900101"
        patient_user.role = User.Role.PATIENT
        patient_user.onboarding_completed = True
        patient_user.set_password("DemoPatient123!")
        patient_user.save()

        patient_profile = sync_user_from_mock_hospital(patient_user, "9001010000")

        assignment, assignment_created = DoctorPatientAssignment.objects.get_or_create(
            doctor=doctor_profile,
            patient=patient_profile,
        )
        medical_patient = ensure_medical_patient(patient_user)
        problem, _ = Problem.objects.update_or_create(
            patient=medical_patient,
            title="Post-pneumonia respiratory follow-up",
            defaults={
                "summary": (
                    "Follow-up after the November 2025 pneumonia admission, with "
                    "intermittent cough and repeat chest imaging."
                ),
                "body_area": "Chest / lungs",
                "keywords": ["pneumonia", "cough", "chest CT", "pulmonology"],
                "embedding_text": (
                    "Post-pneumonia respiratory follow-up involving cough, lungs, "
                    "pulmonology, and repeat chest CT."
                ),
            },
        )
        scan_analysis = {
            "scanType": "CT",
            "bodyPart": "Chest / lungs",
            "imageQuality": "Diagnostic single representative image",
            "visibleAnatomy": ["lungs", "mediastinum", "pleural spaces"],
            "possibleFindings": [
                {
                    "finding": "Mild residual right lower-lobe opacity",
                    "severity": "low",
                    "confidence": 0.78,
                }
            ],
            "simpleExplanation": (
                "A small residual opacity may remain after the recent pneumonia. "
                "Clinical follow-up is recommended."
            ),
            "recommendedDepartment": "Pulmonology / Thoracic Radiology",
            "urgency": "routine",
            "limitations": ["Synthetic demo interpretation; not for clinical use."],
            "disclaimer": "Synthetic seeded AI result for VersaMed testing.",
        }
        scan_diagnosis, _ = Diagnosis.objects.update_or_create(
            patient=medical_patient,
            kind=Diagnosis.Kind.RADIOLOGY,
            title="Follow-up chest CT after pneumonia",
            defaults={
                "happened_at": date(2025, 12, 18),
                "raw_text": (
                    "Follow-up chest CT after inpatient treatment for pneumonia. "
                    "Patient reports an improving intermittent dry cough."
                ),
                "raw_json": {
                    "source": "scan_image_analysis",
                    "scan_id": "tcia_scan_001",
                    "scan": {
                        "id": "tcia_scan_001",
                        "title": "Chest / lungs CT - LIDC-IDRI",
                        "modality": "CT",
                        "bodyPart": "Chest / lungs",
                        "symptoms": ["intermittent dry cough", "recent pneumonia"],
                        "clinicalContext": "Six-week post-pneumonia follow-up.",
                    },
                    "scan_analysis": scan_analysis,
                },
                "description": (
                    "Synthetic follow-up CT record showing a mild residual opacity "
                    "after pneumonia, without seeded urgent findings."
                ),
                "summary": "Mild residual right lower-lobe opacity on follow-up chest CT.",
                "extracted_findings": scan_analysis["possibleFindings"],
                "keywords": ["chest CT", "pneumonia", "residual opacity"],
                "body_areas": ["chest", "lungs"],
                "embedding_text": (
                    "Follow-up chest CT after pneumonia with mild residual "
                    "right lower-lobe opacity."
                ),
            },
        )
        hospitalization_diagnosis, _ = Diagnosis.objects.update_or_create(
            patient=medical_patient,
            kind=Diagnosis.Kind.DOCTOR_DIAGNOSIS,
            title="Pneumonia hospitalization (J18.9)",
            defaults={
                "happened_at": date(2025, 11, 2),
                "raw_text": (
                    "Hospitalized in Pulmonology from 2025-11-02 to 2025-11-06 "
                    "for pneumonia. Improved after inpatient treatment."
                ),
                "raw_json": {
                    "source": "his_hospitalization",
                    "source_id": "hosp-ivan-001",
                    "diagnosis_code": "J18.9",
                    "department": "Pulmonology",
                },
                "description": "Completed inpatient treatment for pneumonia.",
                "summary": "November 2025 inpatient stay for pneumonia.",
                "extracted_findings": [
                    {
                        "name": "Pneumonia",
                        "value": "J18.9",
                        "interpretation": "treated",
                    }
                ],
                "keywords": ["pneumonia", "hospitalization", "pulmonology"],
                "body_areas": ["chest", "lungs"],
                "embedding_text": "Pneumonia hospitalization in Pulmonology.",
            },
        )
        for diagnosis, reason in (
            (
                hospitalization_diagnosis,
                "The hospitalization established the respiratory problem.",
            ),
            (
                scan_diagnosis,
                "The follow-up CT tracks recovery from the same pneumonia episode.",
            ),
        ):
            DiagnosisProblemLink.objects.update_or_create(
                diagnosis=diagnosis,
                problem=problem,
                defaults={
                    "strength": DiagnosisProblemLink.Strength.STRONG,
                    "reason": reason,
                },
            )

        now = timezone.now()
        laboratory_result, _ = LaboratoryResult.objects.update_or_create(
            id=DEMO_LAB_RESULT_ID,
            defaults={
                "patient": patient_profile,
                "laboratory_request": "VM-DEMO-FOLLOWUP-001",
                "laboratory_name": "VersaMed Demo Diagnostic Centre",
                "collected_at": now - timedelta(days=2, hours=2),
                "reported_at": now - timedelta(days=2),
                "status": LaboratoryResult.Status.COMPLETED,
                "test_results": [
                    {
                        "test_name": "Hemoglobin",
                        "value": 146,
                        "unit": "g/L",
                        "reference_range": "135-175",
                        "flag": "normal",
                    },
                    {
                        "test_name": "White blood cells",
                        "value": 7.2,
                        "unit": "10^9/L",
                        "reference_range": "4.0-10.0",
                        "flag": "normal",
                    },
                    {
                        "test_name": "C-reactive protein",
                        "value": 4.1,
                        "unit": "mg/L",
                        "reference_range": "0-5",
                        "flag": "normal",
                    },
                ],
                "created_by": doctor_user,
            },
        )
        attachment = LaboratoryResultAttachment.objects.filter(
            laboratory_result=laboratory_result,
            title="follow-up-chest-ct.png",
        ).first()
        if attachment is None:
            source_scan = settings.BASE_DIR / "media" / "scans" / "tcia_scan_001.png"
            with source_scan.open("rb") as scan_file:
                attachment = LaboratoryResultAttachment(
                    laboratory_result=laboratory_result,
                    file_type=LaboratoryResultAttachment.FileType.IMAGE,
                    title="follow-up-chest-ct.png",
                    description="Synthetic chest CT attached to the complete demo patient.",
                    uploaded_by=doctor_user,
                )
                attachment.file.save("follow-up-chest-ct.png", File(scan_file), save=True)

        AIRun.objects.update_or_create(
            patient=medical_patient,
            diagnosis=scan_diagnosis,
            task="scan_image_analysis",
            defaults={
                "input_context": {
                    "scan_id": "tcia_scan_001",
                    "patient_symptoms": "Improving intermittent dry cough.",
                },
                "output_json": scan_analysis,
                "prompt": "Synthetic deterministic demo scan analysis.",
                "raw_response": "Seeded successfully.",
                "error": "",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "\n".join(
                    [
                        "Demo data is ready.",
                        f"Doctor user: {doctor_user.username} / DemoDoctor123! ({'created' if doctor_created else 'updated'})",
                        f"Patient user: {patient_user.username} / DemoPatient123! ({'created' if patient_created else 'updated'})",
                        f"Doctor-patient assignment: {'created' if assignment_created else 'already existed'}",
                        f"Doctor UIN: {doctor_profile.uin}",
                        f"Patient EGN: {patient_profile.personal_identifier}",
                        f"Medical patient ID: {medical_patient.id}",
                        "Patient record: identity, HIS history, labs, chest CT, diagnoses, problem links, and AI run",
                    ]
                )
            )
        )
