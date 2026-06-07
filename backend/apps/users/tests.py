from django.contrib.auth import get_user_model
from django.test import TestCase


class UserModelTests(TestCase):
    def test_create_user(self):
        user = get_user_model().objects.create_user(
            username="chef",
            email="chef@example.com",
            password="testpass123",
        )

        self.assertEqual(user.email, "chef@example.com")
        self.assertTrue(user.check_password("testpass123"))
