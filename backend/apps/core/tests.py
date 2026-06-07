from django.test import TestCase
from django.urls import reverse


class CoreSmokeTests(TestCase):
    def test_home_page_returns_blank_response(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertIn("csrftoken", response.cookies)
