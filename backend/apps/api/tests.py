import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.core.models import (
    DoctorProfile,
    LaboratoryResult,
    LaboratoryResultAttachment,
    MedicalInstitution,
    PatientProfile,
)
from apps.users.models import DoctorPatientAssignment, User


class LaboratoryResultApiTests(APITestCase):
    endpoint = "/api/laboratory/results/"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_media = tempfile.mkdtemp()
        cls.storage = LaboratoryResultAttachment._meta.get_field("file").storage
        cls.original_location = cls.storage._location
        cls.storage._location = cls.private_media
        cls.storage.__dict__.pop("base_location", None)
        cls.storage.__dict__.pop("location", None)

    @classmethod
    def tearDownClass(cls):
        cls.storage._location = cls.original_location
        cls.storage.__dict__.pop("base_location", None)
        cls.storage.__dict__.pop("location", None)
        shutil.rmtree(cls.private_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="patient-user",
            email="patient-user@example.com",
            password="password123",
            role=User.Role.PATIENT,
        )
        self.patient_profile = PatientProfile.objects.create(
            user=self.user,
            personal_identifier="9001010000",
            birth_date="1990-01-01",
            gender="",
            blood_type="",
            address="",
        )
        self.client.force_authenticate(self.user)

    def upload(self, name="report.pdf", content=b"%PDF-1.4 mock", content_type="application/pdf"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_patient_can_upload_file_for_self(self):
        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["patient_id"], self.patient_profile.id)
        self.assertEqual(len(response.data["attachments"]), 1)
        attachment = LaboratoryResultAttachment.objects.get()
        self.assertEqual(attachment.uploaded_by, self.user)
        self.assertTrue(Path(attachment.file.path).is_file())

    def test_doctor_can_upload_file_for_assigned_patient(self):
        doctor_user = User.objects.create_user(
            username="doctor-user",
            email="doctor-user@example.com",
            password="password123",
            role=User.Role.DOCTOR,
        )
        institution = MedicalInstitution.objects.create(
            name="VersaMed Clinic",
            nhif_number="220012345",
            city="Sofia",
            address="Main St 1",
            phone_number="",
        )
        doctor_profile = DoctorProfile.objects.create(
            user=doctor_user,
            uin="1234567890",
            specialty="General Practice",
            medical_institution=institution,
        )
        DoctorPatientAssignment.objects.create(
            doctor=doctor_profile,
            patient=self.patient_profile,
        )
        self.client.force_authenticate(doctor_user)

        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload("scan.png", b"img", "image/png")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LaboratoryResult.objects.get().patient, self.patient_profile)
        self.assertEqual(LaboratoryResultAttachment.objects.get().uploaded_by, doctor_user)

    def test_doctor_cannot_upload_for_unassigned_patient(self):
        doctor_user = User.objects.create_user(
            username="doctor-two",
            email="doctor-two@example.com",
            password="password123",
            role=User.Role.DOCTOR,
        )
        self.client.force_authenticate(doctor_user)

        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("user_id", response.data)

    def test_rejects_missing_file(self):
        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    def test_rejects_unsupported_attachment_type(self):
        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload("malware.exe", b"nope")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LaboratoryResult.objects.count(), 0)

    @override_settings(LAB_RESULT_MAX_FILE_SIZE=4)
    def test_rejects_attachment_over_configured_size(self):
        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload(content=b"12345")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LaboratoryResult.objects.count(), 0)

    def test_attachment_download_requires_authentication(self):
        create_response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload()},
            format="multipart",
        )
        attachment_id = create_response.data["attachments"][0]["id"]
        download_path = f"{self.endpoint}attachments/{attachment_id}/download/"

        self.client.force_authenticate(user=None)
        unauthorized = self.client.get(download_path)
        self.client.force_authenticate(self.user)
        authorized = self.client.get(download_path)

        self.assertEqual(unauthorized.status_code, 403)
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("attachment;", authorized.headers["Content-Disposition"])

    def test_attachment_download_is_private_to_allowed_users(self):
        create_response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload()},
            format="multipart",
        )
        attachment_id = create_response.data["attachments"][0]["id"]
        other_user = User.objects.create_user(
            username="other-user",
            email="other-user@example.com",
            password="password123",
        )
        self.client.force_authenticate(other_user)

        response = self.client.get(f"{self.endpoint}attachments/{attachment_id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_creation_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.endpoint,
            {"user_id": self.user.id, "file": self.upload()},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
