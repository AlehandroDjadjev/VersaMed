import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

<<<<<<< HEAD
from apps.core.models import LaboratoryResult, LaboratoryResultAttachment
from apps.medical.models import Diagnosis, DiagnosisProblemLink, Patient, Problem
from apps.users.models import User
=======
from apps.core.models import (
    DoctorProfile,
    LaboratoryResult,
    LaboratoryResultAttachment,
    MedicalInstitution,
    PatientProfile,
)
from apps.users.models import DoctorPatientAssignment, User


class AnalyzeScanApiTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scan_id = json.loads((settings.BASE_DIR / "scans.json").read_text())[0]["id"]
        cls.endpoint = f"/api/analyze-scan/{cls.scan_id}"

    def test_requires_patient_symptoms(self):
        response = self.client.post(self.endpoint, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("patient_symptoms", response.data)

    def test_rejects_blank_patient_symptoms(self):
        response = self.client.post(self.endpoint, {"patient_symptoms": "   "}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("patient_symptoms", response.data)

    @patch("apps.api.views.analyze_scan_with_ai")
    def test_passes_patient_symptoms_to_ai_service(self, analyze_scan):
        analyze_scan.return_value = {
            "scanType": "CT",
            "bodyPart": "Chest",
            "imageQuality": "Adequate",
            "visibleAnatomy": [],
            "possibleFindings": [],
            "simpleExplanation": "Mock result.",
            "recommendedDepartment": "Radiology",
            "urgency": "low",
            "limitations": [],
            "disclaimer": "Mock disclaimer.",
        }

        response = self.client.post(
            self.endpoint,
            {"patient_symptoms": "  Cough and chest tightness for three days.  "},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["patientSymptoms"], "Cough and chest tightness for three days.")
        analyze_scan.assert_called_once()
        self.assertEqual(analyze_scan.call_args.args[1], "Cough and chest tightness for three days.")
>>>>>>> ceb6944170cb0cc0d563133e5009f82533b5cd44


def diagnosis_model_output():
    return {
        "diagnosis": {
            "title": "Hospitalization for pneumonia",
            "summary": "The HIS source records an inpatient stay for pneumonia.",
            "description": "This hospitalization should be tracked as a respiratory issue.",
            "extracted_findings": [
                {
                    "name": "Pneumonia",
                    "value": "J18.9",
                    "unit": "",
                    "interpretation": "abnormal",
                    "meaning": "A coded inpatient diagnosis from the HIS source.",
                }
            ],
            "keywords": ["pneumonia", "pulmonology", "hospitalization"],
            "body_areas": ["chest", "lungs"],
        },
        "problem_action": {
            "action": "create_problem",
            "target_problem_id": None,
            "problem": {
                "title": "Recent pneumonia hospitalization",
                "summary": "A synced HIS hospitalization records pneumonia requiring inpatient care.",
                "body_area": "lungs",
                "keywords": ["pneumonia", "respiratory", "hospitalization"],
            },
            "reasoning": "A new hospitalization diagnosis should be tracked as a problem.",
        },
        "links": [
            {
                "problem_id": None,
                "problem_title": "Recent pneumonia hospitalization",
                "strength": "strong",
                "reason": "The diagnosis directly supports the problem.",
            }
        ],
    }


class OnboardingSyncAnalysisTests(APITestCase):
    @patch(
        "apps.medical.services.run_medical_research",
        return_value={
            "query": "pneumonia hospitalization evidence",
            "answer": "Research evidence summary for pneumonia hospitalization.",
            "accepted": [],
            "trace_path": "",
            "answer_path": "",
            "state_path": "",
        },
    )
    @patch(
        "apps.medical.services.generate_research_query",
        return_value=("pneumonia hospitalization evidence", "{}"),
    )
    @patch("apps.medical.services.call_medical_model")
    def test_sync_analyzes_new_his_hospitalization_and_returns_problem(
        self,
        call_medical_model,
        generate_research_query,
        run_medical_research,
    ):
        call_medical_model.return_value = (diagnosis_model_output(), "{}")
        user = User.objects.create_user(
            username="sync-patient",
            email="sync-patient@example.com",
            password="password123",
            role=User.Role.PATIENT,
        )
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/onboarding/sync/",
            {"personal_identifier": "9001010000"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["new_records"]["hospitalizations"], 1)
        self.assertEqual(response.data["new_problem"]["title"], "Recent pneumonia hospitalization")
        self.assertEqual(Patient.objects.filter(user=user).count(), 1)
        self.assertEqual(Diagnosis.objects.count(), 1)
        self.assertEqual(Problem.objects.count(), 1)
        self.assertEqual(DiagnosisProblemLink.objects.count(), 1)

        second_response = self.client.post(
            "/api/onboarding/sync/",
            {"personal_identifier": "9001010000"},
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["new_records"]["hospitalizations"], 0)
        self.assertIsNone(second_response.data["new_problem"])
        self.assertEqual(Diagnosis.objects.count(), 1)


class ScanAnalysisApiTests(APITestCase):
    @patch("apps.api.views.DiagnosisAnalysisService.analyze_and_save")
    @patch("apps.api.views.analyze_scan_with_ai")
    def test_analyze_scan_upload_returns_diagnosis_payload(
        self,
        analyze_scan_with_ai,
        analyze_and_save,
    ):
        analyze_scan_with_ai.return_value = {
            "scanType": "CT",
            "bodyPart": "Chest / lungs",
            "imageQuality": "Limited single image",
            "visibleAnatomy": ["lungs"],
            "possibleFindings": [],
            "simpleExplanation": "Preliminary scan text.",
            "recommendedDepartment": "Radiology",
            "urgency": "medium",
            "limitations": ["Single image only."],
            "disclaimer": "AI generated.",
        }
        user = User.objects.create_user(
            username="scan-user",
            email="scan-user@example.com",
            password="password123",
            role=User.Role.PATIENT,
        )
        patient = Patient.objects.create(user=user, name="Scan User")
        diagnosis = Diagnosis.objects.create(
            patient=patient,
            kind=Diagnosis.Kind.RADIOLOGY,
            title="Uploaded chest scan image analysis",
            raw_text="Generated text",
            raw_json={},
        )
        analyze_and_save.return_value = diagnosis
        self.client.force_authenticate(user)
        upload = SimpleUploadedFile(
            "scan.png",
            (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
                b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

        response = self.client.post(
            "/api/analyze-scan/",
            {
                "patient_id": patient.id,
                "title": "Uploaded chest scan",
                "modality": "CT",
                "body_part": "chest",
                "symptoms": "chest pain,cough",
                "image": upload,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["aiResult"]["scanType"], "CT")
        self.assertEqual(response.data["diagnosis"]["kind"], "radiology")
        self.assertIn("problem_links", response.data)
        analyze_and_save.assert_called_once()
        forwarded = analyze_and_save.call_args.kwargs
        self.assertEqual(forwarded["raw_json"]["source"], "uploaded_scan_analysis")
        self.assertEqual(forwarded["raw_json"]["scan_analysis"]["scanType"], "CT")
        self.assertIn("Preliminary scan analysis", forwarded["raw_text"])

    @patch("apps.api.views.DiagnosisAnalysisService.analyze_and_save")
    @patch("apps.api.views.analyze_scan_with_ai")
    @patch("apps.api.views.scan_image_path")
    def test_analyze_scan_by_id_forwards_to_diagnosis_pipeline(
        self,
        scan_image_path,
        analyze_scan_with_ai,
        analyze_and_save,
    ):
        analyze_scan_with_ai.return_value = {
            "scanType": "CT",
            "bodyPart": "Chest / lungs",
            "imageQuality": "Limited single image",
            "visibleAnatomy": ["lungs"],
            "possibleFindings": [],
            "simpleExplanation": "Preliminary scan text.",
            "recommendedDepartment": "Radiology",
            "urgency": "medium",
            "limitations": ["Single image only."],
            "disclaimer": "AI generated.",
        }
        user = User.objects.create_user(
            username="scan-id-user",
            email="scan-id-user@example.com",
            password="password123",
            role=User.Role.PATIENT,
        )
        patient = Patient.objects.create(user=user, name="Scan Id User")
        diagnosis = Diagnosis.objects.create(
            patient=patient,
            kind=Diagnosis.Kind.RADIOLOGY,
            title="Static scan image analysis",
            raw_text="Generated text",
            raw_json={},
        )
        analyze_and_save.return_value = diagnosis
        self.client.force_authenticate(user)
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        image_path = Path(temp_dir.name) / "tcia_scan_001.png"
        image_path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01"
            b"\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        scan_image_path.return_value = image_path

        response = self.client.post(
            "/api/analyze-scan/tcia_scan_001/",
            {"patient_id": patient.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["aiResult"]["scanType"], "CT")
        analyze_and_save.assert_called_once()
        forwarded = analyze_and_save.call_args.kwargs
        self.assertEqual(forwarded["raw_json"]["source"], "scan_image_analysis")
        self.assertEqual(forwarded["raw_json"]["scan_id"], "tcia_scan_001")
        self.assertEqual(forwarded["raw_json"]["scan_analysis"]["scanType"], "CT")


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
<<<<<<< HEAD
        )
=======
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
        self.base_data = {**self.base_data, "patient_id": self.patient.id}
>>>>>>> ceb6944170cb0cc0d563133e5009f82533b5cd44
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
<<<<<<< HEAD
=======


class EmailNotificationApiTests(APITestCase):
    endpoint = "/api/notifications/email/"
    payload = {
        "to_email": "patient@example.com",
        "subject": "Your VersaMed notification",
        "message": "Your lab result is ready.",
    }

    def setUp(self):
        self.doctor = User.objects.create_user(
            username="notification-doctor",
            email="doctor-notifications@example.com",
            password="password123",
            role=User.Role.DOCTOR,
        )

    @patch("apps.core.email_notifications.send_mail", return_value=1)
    def test_authenticated_doctor_request_succeeds(self, mocked_send_mail):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(self.endpoint, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"success": True, "message": "Email sent successfully."})
        mocked_send_mail.assert_called_once()

    def test_unauthenticated_request_fails(self):
        response = self.client.post(self.endpoint, self.payload, format="json")

        self.assertIn(response.status_code, {401, 403})
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_patient_role_cannot_send_notifications(self):
        patient = User.objects.create_user(
            username="notification-patient",
            email="notification-patient@example.com",
            password="password123",
            role=User.Role.PATIENT,
        )
        self.client.force_authenticate(patient)

        response = self.client.post(self.endpoint, self.payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_invalid_email_fails_validation(self):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(
            self.endpoint,
            {**self.payload, "to_email": "not-an-email"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("to_email", response.data)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_empty_subject_and_message_fail_validation(self):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(
            self.endpoint,
            {**self.payload, "subject": " ", "message": " "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("subject", response.data)
        self.assertIn("message", response.data)
        self.assertEqual(EmailNotification.objects.count(), 0)

    def test_subject_header_injection_fails_validation(self):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(
            self.endpoint,
            {**self.payload, "subject": "Valid subject\r\nBcc: attacker@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("subject", response.data)
        self.assertEqual(EmailNotification.objects.count(), 0)

    @patch("apps.core.email_notifications.send_mail", side_effect=RuntimeError("SMTP secret detail"))
    def test_smtp_failure_sets_failed_status_and_returns_generic_error(self, mocked_send_mail):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(self.endpoint, self.payload, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data, {"success": False, "message": "Failed to send email."})
        self.assertNotIn("SMTP secret detail", str(response.data))
        notification = EmailNotification.objects.get()
        self.assertEqual(notification.status, EmailNotification.Status.FAILED)
        self.assertIsNone(notification.sent_at)
        self.assertIn("RuntimeError", notification.error_message)
        mocked_send_mail.assert_called_once()

    @patch("apps.core.email_notifications.send_mail", return_value=1)
    def test_successful_send_sets_sent_status_and_creates_correct_record(self, mocked_send_mail):
        self.client.force_authenticate(self.doctor)

        response = self.client.post(self.endpoint, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        notification = EmailNotification.objects.get()
        self.assertEqual(notification.user, self.doctor)
        self.assertEqual(notification.to_email, self.payload["to_email"])
        self.assertEqual(notification.subject, self.payload["subject"])
        self.assertEqual(notification.message, self.payload["message"])
        self.assertEqual(notification.status, EmailNotification.Status.SENT)
        self.assertIsNotNone(notification.sent_at)
        self.assertIsNone(notification.error_message)
        mocked_send_mail.assert_called_once_with(
            subject=self.payload["subject"],
            message=self.payload["message"],
            from_email="VersaMed <versamedvm@gmail.com>",
            recipient_list=[self.payload["to_email"]],
            fail_silently=False,
        )

    @patch("apps.core.email_notifications.send_mail")
    @override_settings(EMAIL_HOST_PASSWORD="super-secret-app-password")
    def test_failure_record_redacts_email_password(self, mocked_send_mail):
        mocked_send_mail.side_effect = RuntimeError("super-secret-app-password was rejected")
        self.client.force_authenticate(self.doctor)

        self.client.post(self.endpoint, self.payload, format="json")

        error_message = EmailNotification.objects.get().error_message
        self.assertNotIn("super-secret-app-password", error_message)
        self.assertIn("[REDACTED]", error_message)
>>>>>>> ceb6944170cb0cc0d563133e5009f82533b5cd44
