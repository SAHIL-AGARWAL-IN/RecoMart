from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class UserRoleTests(TestCase):
    def test_new_users_are_customers(self):
        user = User.objects.create_user("ravi", password="Testpass@123")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_store_admin)

    def test_admin_role_is_store_admin(self):
        user = User.objects.create_user("meera", password="Testpass@123", role=User.Role.ADMIN)
        self.assertTrue(user.is_store_admin)

    def test_superuser_is_always_store_admin(self):
        user = User.objects.create_superuser("root", password="Testpass@123")
        self.assertTrue(user.is_store_admin)

    def test_password_is_hashed(self):
        user = User.objects.create_user("kiran", password="Testpass@123")
        self.assertNotEqual(user.password, "Testpass@123")
        self.assertTrue(user.check_password("Testpass@123"))
