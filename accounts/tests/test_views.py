from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegisterTests(TestCase):
    def form_data(self, **overrides):
        data = {"first_name": "Asha", "last_name": "Rao", "username": "asha", "email": "asha@example.com",
                "password1": "Shopping@2026", "password2": "Shopping@2026"}
        data.update(overrides)
        return data

    def test_register_creates_a_logged_in_customer(self):
        response = self.client.post(reverse("accounts:register"), self.form_data())
        self.assertRedirects(response, reverse("store:home"))
        user = User.objects.get(username="asha")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.check_password("Shopping@2026"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("other", email="asha@example.com", password="Shopping@2026")
        response = self.client.post(reverse("accounts:register"), self.form_data())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "email",
                             "An account with this email already exists. Try logging in.")

    def test_register_ignores_unsafe_next_url(self):
        response = self.client.post(reverse("accounts:register"), self.form_data(next="https://evil.example/"))
        self.assertRedirects(response, reverse("store:home"))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("vikram", password="Shopping@2026", first_name="Vikram")

    def test_login_with_valid_credentials(self):
        response = self.client.post(reverse("accounts:login"), {"username": "vikram", "password": "Shopping@2026"})
        self.assertRedirects(response, reverse("store:home"))

    def test_login_with_wrong_password_shows_error(self):
        response = self.client.post(reverse("accounts:login"), {"username": "vikram", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileTests(TestCase):
    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_profile_update(self):
        user = User.objects.create_user("meena", password="Shopping@2026")
        self.client.force_login(user)
        self.client.post(reverse("accounts:profile"),
                         {"first_name": "Meena", "last_name": "Iyer", "email": "meena@example.com", "phone": "9876543210"})
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), "Meena Iyer")
