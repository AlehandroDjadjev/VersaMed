from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class UserModelTests(TestCase):
    def test_create_user(self):
        user = get_user_model().objects.create_user(
            username="chef",
            email="chef@example.com",
            password="testpass123",
        )

        self.assertEqual(user.email, "chef@example.com")
        self.assertTrue(user.check_password("testpass123"))

    def test_email_is_normalized_on_save(self):
        user = get_user_model().objects.create_user(
            username="lowercase",
            email="UPPER@Example.COM",
            password="testpass123",
        )

        self.assertEqual(user.email, "upper@example.com")


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def test_signup_creates_user_and_logs_them_in(self):
        self.client.get(reverse("home"))
        response = self.client.post(
            reverse("users:signup"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "VerySecurePass123",
                "password_confirm": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["username"], "newuser")
        self.assertEqual(self.client.get(reverse("users:me")).status_code, 200)

    def test_signup_rejects_weak_passwords(self):
        self.client.get(reverse("home"))
        response = self.client.post(
            reverse("users:signup"),
            {
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "123",
                "password_confirm": "123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_login_logout_and_me_flow(self):
        get_user_model().objects.create_user(
            username="existing",
            email="existing@example.com",
            password="VerySecurePass123",
        )
        self.client.get(reverse("home"))
        csrf_token = self.client.cookies["csrftoken"].value

        login_response = self.client.post(
            reverse("users:login"),
            {
                "username": "existing",
                "password": "VerySecurePass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        refreshed_csrf_token = self.client.cookies["csrftoken"].value
        me_response = self.client.get(reverse("users:me"))
        logout_response = self.client.post(
            reverse("users:logout"),
            format="json",
            HTTP_X_CSRFTOKEN=refreshed_csrf_token,
        )
        post_logout_me_response = self.client.get(reverse("users:me"))

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(logout_response.status_code, 204)
        self.assertEqual(post_logout_me_response.status_code, 403)

    def test_login_rejects_invalid_credentials(self):
        self.client.get(reverse("home"))
        response = self.client.post(
            reverse("users:login"),
            {
                "username": "missing",
                "password": "wrongpass123",
            },
            format="json",
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["non_field_errors"],
            ["Invalid username or password."],
        )
