from datetime import date, datetime
from xml.etree import ElementTree

from django.test import TestCase, override_settings

from . import fake_data


class HisMockTests(TestCase):
    xml_body = "<Request><PatientId>9001010000</PatientId></Request>"

    endpoint_contracts = [
        ("post", "/v1/nomenclatures/all/get", "C002"),
        ("post", "/v1/nomenclatures/all/vaccinelotnumber", "C004"),
        ("post", "/v1/eimmunization/immunization/issue", "I002"),
        ("post", "/v1/eimmunization/immunization/fetch", "I004"),
        ("post", "/v1/eimmunization/immunization/certificate", "I014"),
        ("post", "/v1/ehospitalization/hospitalization/fetch", "H002"),
        ("get", "/v1/ehospitalization/epicrisis", "MOCK_EPICRISIS"),
    ]

    def request_endpoint(self, method, path, **extra):
        if method == "post":
            return self.client.post(
                path,
                data=self.xml_body,
                content_type="application/xml",
                **extra,
            )
        return self.client.get(path, **extra)

    def parse_xml_response(self, response):
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        try:
            return ElementTree.fromstring(response.content)
        except ElementTree.ParseError as error:
            self.fail(f"Response is not valid XML: {error}")

    def assert_success_envelope(self, response, expected_code):
        self.assertEqual(response.status_code, 200)
        root = self.parse_xml_response(response)
        self.assertEqual(root.tag, "Response")
        self.assertEqual(
            [child.tag for child in root],
            ["Status", "Code", "Message", "RequestId", "Timestamp", "Data"],
        )
        self.assertEqual(root.findtext("Status"), "SUCCESS")
        self.assertEqual(root.findtext("Code"), expected_code)
        self.assertTrue(root.findtext("Message"))
        self.assertEqual(root.findtext("RequestId"), fake_data.REQUEST_ID)
        self.assertEqual(root.findtext("Timestamp"), fake_data.TIMESTAMP)
        self.assertIsNotNone(root.find("Data"))
        datetime.fromisoformat(root.findtext("Timestamp").replace("Z", "+00:00"))
        return root

    def assert_mapping(self, parent, expected):
        self.assertEqual([child.tag for child in parent], list(expected))
        self.assertEqual(
            {child.tag: child.text for child in parent},
            {key: str(value) for key, value in expected.items()},
        )

    def assert_error_envelope(self, response, status, code):
        self.assertEqual(response.status_code, status)
        root = self.parse_xml_response(response)
        self.assertEqual(root.tag, "Response")
        self.assertEqual(root.findtext("Status"), "ERROR")
        self.assertEqual(root.findtext("Code"), code)
        self.assertTrue(root.findtext("Message"))
        self.assertEqual(root.findtext("HttpStatus"), str(status))
        self.assertIsNone(root.find("Data"))
        return root

    def assert_valid_egn(self, value):
        self.assertRegex(value, r"^\d{10}$")
        weights = [2, 4, 8, 5, 10, 9, 7, 3, 6]
        checksum = sum(int(digit) * weight for digit, weight in zip(value[:9], weights, strict=True)) % 11
        expected = 0 if checksum == 10 else checksum
        self.assertEqual(int(value[-1]), expected)

    def test_every_endpoint_has_valid_success_envelope_and_expected_code(self):
        for method, path, code in self.endpoint_contracts:
            with self.subTest(path=path):
                response = self.request_endpoint(
                    method,
                    path,
                    HTTP_AUTHORIZATION="Bearer mock-token",
                )
                self.assert_success_envelope(response, code)

    def test_nomenclature_response_matches_fake_data(self):
        root = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/nomenclatures/all/get"),
            "C002",
        )
        items = root.findall("./Data/Nomenclatures/Nomenclature")
        self.assertEqual(len(items), len(fake_data.NOMENCLATURES))
        for item, expected in zip(items, fake_data.NOMENCLATURES, strict=True):
            self.assert_mapping(item, expected)
            self.assertTrue(item.findtext("Code"))
            self.assertTrue(item.findtext("Name"))

    def test_vaccine_lot_response_matches_fake_data_and_has_valid_dates(self):
        root = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/nomenclatures/all/vaccinelotnumber"),
            "C004",
        )
        lots = root.findall("./Data/VaccineLotNumbers/VaccineLotNumber")
        self.assertEqual(len(lots), len(fake_data.VACCINE_LOTS))
        for lot, expected in zip(lots, fake_data.VACCINE_LOTS, strict=True):
            self.assert_mapping(lot, expected)
            date.fromisoformat(lot.findtext("ExpiryDate"))

    def test_immunization_issue_and_certificate_ids_are_consistent(self):
        issue = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/eimmunization/immunization/issue"),
            "I002",
        )
        certificate = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/eimmunization/immunization/certificate"),
            "I014",
        )
        self.assertEqual(
            [child.tag for child in issue.find("Data")],
            ["DocumentId", "CertificateId"],
        )
        self.assertEqual(issue.findtext("./Data/DocumentId"), fake_data.DOCUMENT_ID)
        self.assertEqual(issue.findtext("./Data/CertificateId"), fake_data.CERTIFICATE_ID)
        self.assertEqual(certificate.findtext("./Data/DocumentId"), fake_data.DOCUMENT_ID)
        self.assertEqual(certificate.findtext("./Data/CertificateId"), fake_data.CERTIFICATE_ID)
        self.assertEqual(certificate.findtext("./Data/CertificateStatus"), "VALID")

    def test_immunization_fetch_matches_all_fake_records(self):
        root = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/eimmunization/immunization/fetch"),
            "I004",
        )
        data = root.find("Data")
        self.assertEqual(
            [child.tag for child in data],
            ["Patient", "Doctor", "MedicalInstitution", "Immunization"],
        )
        self.assert_mapping(data.find("Patient"), fake_data.PATIENT)
        self.assert_mapping(data.find("Doctor"), fake_data.DOCTOR)
        self.assert_mapping(data.find("MedicalInstitution"), fake_data.MEDICAL_INSTITUTION)
        self.assert_mapping(data.find("Immunization"), fake_data.IMMUNIZATION)
        date.fromisoformat(data.findtext("./Patient/BirthDate"))
        date.fromisoformat(data.findtext("./Immunization/Date"))
        self.assert_valid_egn(data.findtext("./Patient/Identifier"))
        self.assertRegex(data.findtext("./Doctor/UIN"), r"^\d{10}$")
        self.assertRegex(data.findtext("./MedicalInstitution/NHIFNumber"), r"^\d{9}$")
        self.assertEqual(data.findtext("./Immunization/DocumentId"), fake_data.DOCUMENT_ID)
        self.assertGreater(int(data.findtext("./Immunization/DoseNumber")), 0)

    def test_hospitalization_fetch_matches_fake_records_and_valid_date_order(self):
        root = self.assert_success_envelope(
            self.request_endpoint("post", "/v1/ehospitalization/hospitalization/fetch"),
            "H002",
        )
        data = root.find("Data")
        self.assertEqual(
            [child.tag for child in data],
            ["Patient", "MedicalInstitution", "Hospitalization"],
        )
        self.assert_mapping(data.find("Patient"), fake_data.PATIENT)
        self.assert_mapping(data.find("MedicalInstitution"), fake_data.MEDICAL_INSTITUTION)
        self.assert_mapping(data.find("Hospitalization"), fake_data.HOSPITALIZATION)
        admission = date.fromisoformat(data.findtext("./Hospitalization/AdmissionDate"))
        discharge = date.fromisoformat(data.findtext("./Hospitalization/DischargeDate"))
        self.assertLessEqual(admission, discharge)

    def test_epicrisis_matches_hospitalization_and_fake_data(self):
        root = self.assert_success_envelope(
            self.request_endpoint("get", "/v1/ehospitalization/epicrisis"),
            "MOCK_EPICRISIS",
        )
        data = root.find("Data")
        self.assert_mapping(data.find("Patient"), fake_data.PATIENT)
        self.assert_mapping(data.find("Epicrisis"), fake_data.EPICRISIS)
        self.assertEqual(
            data.findtext("./Epicrisis/HospitalizationId"),
            fake_data.HOSPITALIZATION["DocumentId"],
        )

    @override_settings(MOCK_AUTH_DISABLED=False)
    def test_missing_auth_returns_complete_401_error(self):
        response = self.request_endpoint("post", "/v1/eimmunization/immunization/fetch")
        self.assert_error_envelope(response, 401, "AUTH_REQUIRED")

    @override_settings(MOCK_FORCE_ERROR=True, MOCK_ERROR_STATUS=503)
    def test_forced_error_mode_returns_complete_error_for_every_endpoint(self):
        for method, path, _ in self.endpoint_contracts:
            with self.subTest(path=path):
                response = self.request_endpoint(method, path)
                self.assert_error_envelope(response, 503, "MOCK_FORCED_ERROR")

    def test_catch_all_returns_complete_error_with_requested_path(self):
        path = "/v1/not/implemented"
        root = self.assert_error_envelope(self.client.get(path), 501, "MOCK_NOT_IMPLEMENTED")
        self.assertEqual(root.findtext("Path"), path)

    def test_non_xml_post_returns_complete_415_error(self):
        response = self.client.post(
            "/v1/eimmunization/immunization/fetch",
            data="not xml",
            content_type="text/plain",
        )
        self.assert_error_envelope(response, 415, "XML_REQUIRED")

    def test_wrong_method_returns_complete_405_error(self):
        response = self.client.get("/v1/eimmunization/immunization/fetch")
        self.assert_error_envelope(response, 405, "METHOD_NOT_ALLOWED")
