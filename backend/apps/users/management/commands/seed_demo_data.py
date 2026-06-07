from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError

from apps.core.models import DoctorProfile, MedicalInstitution, PatientProfile
from apps.core.services import sync_user_from_mock_hospital
from apps.users.models import DoctorPatientAssignment


User = get_user_model()


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
            username="demo_doctor",
            defaults={
                "email": "doctor.demo@versamed.app",
                "first_name": "Elena",
                "middle_name": "Stoyanova",
                "last_name": "Georgieva",
                "role": User.Role.DOCTOR,
                "onboarding_completed": True,
            },
        )
        doctor_user.email = "doctor.demo@versamed.app"
        doctor_user.first_name = "Elena"
        doctor_user.middle_name = "Stoyanova"
        doctor_user.last_name = "Georgieva"
        doctor_user.role = User.Role.DOCTOR
        doctor_user.onboarding_completed = True
        doctor_user.set_password("DemoDoctor123!")
        doctor_user.save()

        doctor_profile = sync_user_from_mock_hospital(doctor_user, "1234567890")

        patient_user, patient_created = User.objects.get_or_create(
            username="demo_patient",
            defaults={
                "email": "patient.demo@versamed.app",
                "first_name": "Ivan",
                "middle_name": "Petrov",
                "last_name": "Ivanov",
                "role": User.Role.PATIENT,
                "onboarding_completed": True,
            },
        )
        patient_user.email = "patient.demo@versamed.app"
        patient_user.first_name = "Ivan"
        patient_user.middle_name = "Petrov"
        patient_user.last_name = "Ivanov"
        patient_user.role = User.Role.PATIENT
        patient_user.onboarding_completed = True
        patient_user.set_password("DemoPatient123!")
        patient_user.save()

        patient_profile = sync_user_from_mock_hospital(patient_user, "9001010000")

        assignment, assignment_created = DoctorPatientAssignment.objects.get_or_create(
            doctor=doctor_profile,
            patient=patient_profile,
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
                    ]
                )
            )
        )
