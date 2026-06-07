import json
import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.core.models import LaboratoryResult, LaboratoryResultAttachment
from apps.users.models import User


class LaboratoryResultApiTests(APITestCase):
    endpoint = "/api/laboratory/results/"
    base_data = {
        "laboratory_request": "lab-request-123",
        "laboratory_name": "Mock Clinical Laboratory",
        "collected_at": "2026-06-07T08:00:00Z",
        "reported_at": "2026-06-07T10:00:00Z",
    }

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
        self.user = User.objects.create_user(username="lab-user", password="password123")
        self.client.force_authenticate(self.user)

    def upload(self, name="report.pdf", content=b"%PDF-1.4 mock", content_type="application/pdf"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    def test_creates_structured_only_result(self):
        data = {
            **self.base_data,
            "test_results": [
                {"test_name": "CRP", "value": 18, "unit": "mg/L", "flag": "HIGH"},
            ],
        }

        response = self.client.post(self.endpoint, data, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["summary"], "1 structured value and 0 attachments uploaded.")
        self.assertEqual(response.data["test_results"], data["test_results"])
        self.assertEqual(response.data["attachments"], [])

    def test_creates_attachment_only_result_without_exposing_file_url(self):
        data = {**self.base_data, "test_results": "[]", "attachments[]": self.upload()}

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["summary"], "0 structured values and 1 attachment uploaded.")
        self.assertNotIn("file", response.data["attachments"][0])
        self.assertNotIn("url", response.data["attachments"][0])
        attachment = LaboratoryResultAttachment.objects.get()
        self.assertEqual(attachment.file_type, "pdf")
        self.assertEqual(attachment.uploaded_by, self.user)
        self.assertTrue(Path(attachment.file.path).is_file())
        with self.assertRaisesMessage(ValueError, "Private files do not have public URLs."):
            attachment.file.url

    def test_creates_mixed_result_with_multiple_attachments(self):
        values = [
            {"test_name": "Hemoglobin", "value": 145, "unit": "g/L", "flag": "NORMAL"},
            {"test_name": "Glucose", "value": 5.4, "unit": "mmol/L", "flag": "NORMAL"},
        ]
        data = {
            **self.base_data,
            "test_results": json.dumps(values),
            "attachments[]": [
                self.upload(),
                self.upload("microscopy.png", b"mock png", "image/png"),
            ],
        }

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["summary"], "2 structured values and 2 attachments uploaded.")
        self.assertEqual({item["file_type"] for item in response.data["attachments"]}, {"pdf", "image"})
        self.assertEqual(LaboratoryResult.objects.get().test_results, values)

    def test_rejects_result_without_values_or_attachments(self):
        response = self.client.post(self.endpoint, {**self.base_data, "test_results": []}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LaboratoryResult.objects.count(), 0)

    def test_rejects_invalid_structured_results(self):
        response = self.client.post(
            self.endpoint,
            {**self.base_data, "test_results": [{"value": 18}]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("test_results", response.data)

    def test_rejects_unsupported_attachment_type(self):
        data = {**self.base_data, "attachments[]": self.upload("malware.exe", b"not allowed")}

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LaboratoryResult.objects.count(), 0)

    @override_settings(LAB_RESULT_MAX_FILE_SIZE=4)
    def test_rejects_attachment_over_configured_size(self):
        data = {**self.base_data, "attachments[]": self.upload(content=b"12345")}

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(LaboratoryResult.objects.count(), 0)

    def test_dicom_is_disabled_by_default(self):
        data = {**self.base_data, "attachments[]": self.upload("scan.dcm", b"DICOM", "application/dicom")}

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 400)

    @override_settings(LAB_RESULT_ALLOW_DICOM=True)
    def test_dicom_can_be_enabled(self):
        data = {**self.base_data, "attachments[]": self.upload("scan.dcm", b"DICOM", "application/dicom")}

        response = self.client.post(self.endpoint, data, format="multipart")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["attachments"][0]["file_type"], "dicom")

    def test_attachment_download_requires_authentication(self):
        create_response = self.client.post(
            self.endpoint,
            {**self.base_data, "attachments[]": self.upload()},
            format="multipart",
        )
        attachment_id = create_response.data["attachments"][0]["id"]
        download_path = f"{self.endpoint}attachments/{attachment_id}/download/"

        self.client.force_authenticate(user=None)
        unauthorized = self.client.get(download_path)
        self.client.force_authenticate(self.user)
        authorized = self.client.get(download_path)

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("attachment;", authorized.headers["Content-Disposition"])

    def test_attachment_download_is_private_to_result_owner(self):
        create_response = self.client.post(
            self.endpoint,
            {**self.base_data, "attachments[]": self.upload()},
            format="multipart",
        )
        attachment_id = create_response.data["attachments"][0]["id"]
        other_user = User.objects.create_user(username="other-user", password="password123")
        self.client.force_authenticate(other_user)

        response = self.client.get(f"{self.endpoint}attachments/{attachment_id}/download/")

        self.assertEqual(response.status_code, 404)

    def test_creation_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.endpoint,
            {**self.base_data, "test_results": [{"test_name": "CRP", "value": 18}]},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
