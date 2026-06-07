from django.test import TestCase, override_settings


class HisMockTests(TestCase):
    endpoint = "/v1/eimmunization/immunization/fetch"
    xml_body = "<Request><PatientId>9001010000</PatientId></Request>"

    def test_valid_xml_post_returns_xml_success(self):
        response = self.client.post(
            self.endpoint,
            data=self.xml_body,
            content_type="application/xml",
            HTTP_AUTHORIZATION="Bearer mock-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        self.assertContains(response, "<Status>SUCCESS</Status>")
        self.assertContains(response, "<Immunization>")

    @override_settings(MOCK_AUTH_DISABLED=False)
    def test_missing_auth_returns_401_when_auth_is_enabled(self):
        response = self.client.post(
            self.endpoint,
            data=self.xml_body,
            content_type="application/xml",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        self.assertContains(response, "<Code>AUTH_REQUIRED</Code>", status_code=401)

    @override_settings(MOCK_FORCE_ERROR=True, MOCK_ERROR_STATUS=503)
    def test_forced_error_mode_uses_configured_status(self):
        response = self.client.post(
            self.endpoint,
            data=self.xml_body,
            content_type="application/xml",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        self.assertContains(response, "<Code>MOCK_FORCED_ERROR</Code>", status_code=503)

    def test_catch_all_returns_clear_xml_error(self):
        response = self.client.get("/v1/not/implemented")

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        self.assertContains(response, "<Code>MOCK_NOT_IMPLEMENTED</Code>", status_code=501)

    def test_non_xml_post_returns_xml_error(self):
        response = self.client.post(self.endpoint, data="not xml", content_type="text/plain")

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.headers["Content-Type"], "application/xml")
        self.assertContains(response, "<Code>XML_REQUIRED</Code>", status_code=415)
