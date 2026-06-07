from datetime import date
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.core.models import DoctorProfile, LaboratoryResult, MedicalInstitution, PatientProfile
from apps.medical.models import Patient

from .models import DoctorPatientAssignment


User = get_user_model()


def latest_verification_code():
    body = mail.outbox[-1].body
    match = re.search(r"(\d{6})", body)
    if not match:
        raise AssertionError("Verification code email was sent without a 6-digit code.")
    return match.group(1)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            username="chef",
            email="chef@example.com",
            password="testpass123",
        )

        self.assertEqual(user.email, "chef@example.com")
        self.assertTrue(user.check_password("testpass123"))

    def test_email_is_normalized_on_save(self):
        user = User.objects.create_user(
            username="lowercase",
            email="UPPER@Example.COM",
            password="testpass123",
        )

        self.assertEqual(user.email, "upper@example.com")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_token(self):
        self.client.get(reverse("home"))
        return self.client.cookies["csrftoken"].value

    def test_csrf_endpoint_sets_cookie(self):
        response = self.client.get(reverse("users:csrf"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", self.client.cookies)

    def complete_login(self, username, password):
        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": username,
                "password": password,
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )
        self.assertEqual(challenge_response.status_code, 202)

        verify_response = self.client.post(
            reverse("users:login-verify"),
            {
                "challenge_id": challenge_response.json()["challenge_id"],
                "code": latest_verification_code(),
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(verify_response.status_code, 200)
        return verify_response

    def test_patient_signup_creates_profile_and_logs_them_in(self):
        response = self.client.post(
            reverse("users:signup-patient"),
            {
                "username": "newpatient",
                "email": "patient@example.com",
                "password": "VerySecurePass123",
                "password_confirm": "VerySecurePass123",
                "first_name": "Ivan",
                "middle_name": "Petrov",
                "last_name": "Ivanov",
                "birth_date": "1990-01-01",
                "egn": "9001010000",
                "gender": "male",
                "blood_type": "A+",
                "address": "Sofia, Synthetic District",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], User.Role.PATIENT)
        self.assertEqual(response.json()["user"]["patient_profile"]["egn"], "9001010000")
        self.assertEqual(response.json()["user"]["patient_profile"]["blood_type"], "A+")
        self.assertTrue(PatientProfile.objects.filter(personal_identifier="9001010000").exists())
        self.assertEqual(self.client.get(reverse("users:me")).status_code, 200)

    def test_doctor_signup_creates_profile_and_logs_them_in(self):
        response = self.client.post(
            reverse("users:signup-doctor"),
            {
                "username": "newdoctor",
                "email": "doctor@example.com",
                "password": "VerySecurePass123",
                "password_confirm": "VerySecurePass123",
                "first_name": "Elena",
                "middle_name": "Stoyanova",
                "last_name": "Georgieva",
                "uin": "1234567890",
                "specialty": "General Practice",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], User.Role.DOCTOR)
        self.assertEqual(
            response.json()["user"]["doctor_profile"]["specialty"],
            "General Practice",
        )
        self.assertTrue(DoctorProfile.objects.filter(uin="1234567890").exists())

    def test_signup_rejects_weak_passwords(self):
        response = self.client.post(
            reverse("users:signup-patient"),
            {
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "123",
                "password_confirm": "123",
                "first_name": "Ivan",
                "middle_name": "Petrov",
                "last_name": "Ivanov",
                "birth_date": "1990-01-01",
                "egn": "9001010000",
                "gender": "male",
                "blood_type": "A+",
                "address": "Sofia, Synthetic District",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_login_logout_and_me_flow(self):
        user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="VerySecurePass123",
            role=User.Role.PATIENT,
        )
        PatientProfile.objects.create(
            user=user,
            personal_identifier="9001010000",
            birth_date=date(1990, 1, 1),
            gender="",
            blood_type="",
            address="",
        )

        self.complete_login("existing", "VerySecurePass123")
        refreshed_csrf_token = self.client.cookies["csrftoken"].value
        me_response = self.client.get(reverse("users:me"))
        logout_response = self.client.post(
            reverse("users:logout"),
            format="json",
            HTTP_X_CSRFTOKEN=refreshed_csrf_token,
        )
        post_logout_me_response = self.client.get(reverse("users:me"))

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(post_logout_me_response.status_code, 200)
        self.assertIsNone(post_logout_me_response.json()["user"])

    def test_login_accepts_email_identifier(self):
        user = User.objects.create_user(
            username="byemail",
            email="byemail@example.com",
            password="VerySecurePass123",
            role=User.Role.PATIENT,
        )
        PatientProfile.objects.create(
            user=user,
            personal_identifier="8001010000",
            birth_date=date(1980, 1, 1),
            gender="female",
            blood_type="O+",
            address="Sofia",
        )

        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "byemail@example.com",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(challenge_response.status_code, 202)
        self.assertEqual(challenge_response.json()["email"], "byemail@example.com")

    def test_login_accepts_patient_egn_identifier(self):
        user = User.objects.create_user(
            username="byegn",
            email="byegn@example.com",
            password="VerySecurePass123",
            role=User.Role.PATIENT,
        )
        PatientProfile.objects.create(
            user=user,
            personal_identifier="8101010000",
            birth_date=date(1981, 1, 1),
            gender="female",
            blood_type="B+",
            address="Plovdiv",
        )

        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "8101010000",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(challenge_response.status_code, 202)
        self.assertEqual(challenge_response.json()["email"], "byegn@example.com")

    def test_login_accepts_doctor_uin_identifier(self):
        institution = MedicalInstitution.objects.create(
            name="Doctor Login Clinic",
            nhif_number="220019999",
            city="Sofia",
            address="Doctor St 9",
            phone_number="",
        )
        user = User.objects.create_user(
            username="byuin",
            email="byuin@example.com",
            password="VerySecurePass123",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=user,
            uin="9988776655",
            specialty="Cardiology",
            medical_institution=institution,
        )

        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "9988776655",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(challenge_response.status_code, 202)
        self.assertEqual(challenge_response.json()["email"], "byuin@example.com")

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "missing",
                "password": "wrongpass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["non_field_errors"],
            ["Invalid login or password."],
        )


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class DoctorAssignmentTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.institution = MedicalInstitution.objects.create(
            name="VersaMed Clinic",
            nhif_number="220012345",
            city="Sofia",
            address="Main St 1",
            phone_number="",
        )
        self.patient_user = User.objects.create_user(
            username="patientone",
            email="patient1@example.com",
            password="VerySecurePass123",
            role=User.Role.PATIENT,
            first_name="Ivan",
            middle_name="Petrov",
            last_name="Ivanov",
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.patient_user,
            personal_identifier="9001010000",
            birth_date=date(1990, 1, 1),
            gender="",
            blood_type="",
            address="",
        )
        self.doctor_user = User.objects.create_user(
            username="doctorone",
            email="doctor1@example.com",
            password="VerySecurePass123",
            role=User.Role.DOCTOR,
            first_name="Elena",
            middle_name="Stoyanova",
            last_name="Georgieva",
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            uin="1234567890",
            specialty="General Practice",
            medical_institution=self.institution,
        )

    def login_doctor(self):
        self.client.get(reverse("home"))
        csrf_token = self.client.cookies["csrftoken"].value
        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "doctorone",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(challenge_response.status_code, 202)
        verify_response = self.client.post(
            reverse("users:login-verify"),
            {
                "challenge_id": challenge_response.json()["challenge_id"],
                "code": latest_verification_code(),
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(verify_response.status_code, 200)
        return self.client.cookies["csrftoken"].value

    def test_doctor_can_assign_patient_by_egn_and_three_names(self):
        csrf_token = self.login_doctor()

        response = self.client.post(
            reverse("users:doctor-patients"),
            {
                "egn": "9001010000",
                "first_name": "Ivan",
                "middle_name": "Petrov",
                "last_name": "Ivanov",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["created"])
        self.assertTrue(
            DoctorPatientAssignment.objects.filter(
                doctor=self.doctor_profile,
                patient=self.patient_profile,
            ).exists()
        )

    def test_doctor_can_list_assigned_patients(self):
        DoctorPatientAssignment.objects.create(
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        self.login_doctor()

        response = self.client.get(reverse("users:doctor-patients"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["assignments"]), 1)
        self.assertEqual(
            response.json()["assignments"][0]["patient"]["egn"],
            "9001010000",
        )

    def test_patient_cannot_access_doctor_assignment_endpoint(self):
        challenge_response = self.client.post(
            reverse("users:login"),
            {
                "login_id": "patientone",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.get(reverse("home")).cookies["csrftoken"].value,
        )
        self.assertEqual(challenge_response.status_code, 202)
        verify_response = self.client.post(
            reverse("users:login-verify"),
            {
                "challenge_id": challenge_response.json()["challenge_id"],
                "code": latest_verification_code(),
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(verify_response.status_code, 200)

        response = self.client.get(reverse("users:doctor-patients"))

        self.assertEqual(response.status_code, 403)

    def test_doctor_can_load_assigned_patient_workspace(self):
        assignment = DoctorPatientAssignment.objects.create(
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        self.login_doctor()

        response = self.client.get(
            reverse(
                "users:doctor-patient-workspace",
                kwargs={"assignment_id": assignment.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["patient_dashboard"]["patient"]["egn"],
            "9001010000",
        )
        self.assertIn("medical_workspace", response.json())
        self.assertTrue(Patient.objects.filter(user=self.patient_user).exists())

    def test_doctor_can_upload_lab_file_for_selected_patient(self):
        assignment = DoctorPatientAssignment.objects.create(
            doctor=self.doctor_profile,
            patient=self.patient_profile,
        )
        csrf_token = self.login_doctor()

        response = self.client.post(
            reverse("api:laboratory-result-create"),
            {
                "user_id": assignment.patient.user_id,
                "file": SimpleUploadedFile(
                    "result.pdf",
                    b"%PDF-1.4 mock",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LaboratoryResult.objects.count(), 1)
        self.assertEqual(LaboratoryResult.objects.get().patient, self.patient_profile)
        self.assertEqual(
            response.json()["patient_egn"],
            "9001010000",
        )
