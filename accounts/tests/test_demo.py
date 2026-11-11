"""Public demo mode: one-click demo logins and the read-only shared demo accounts."""
import shutil
import tempfile

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.demo import DEMO_ADMIN, DEMO_CUSTOMER
from recommender import engine
from store.models import Product
from store.tests.factories import make_category, make_product, make_user

PROFILE = {"first_name": "Changed", "last_name": "Name", "email": "changed@example.com", "phone": "9876543210"}


def make_demo_accounts():
    """The two shared accounts, as seed_data creates them (the admin is a superuser)."""
    admin = make_user(DEMO_ADMIN["username"], password=DEMO_ADMIN["password"], first_name="Store",
                      role="admin", is_staff=True, is_superuser=True)
    priya = make_user(DEMO_CUSTOMER["username"], password=DEMO_CUSTOMER["password"], first_name="Priya")
    return admin, priya


@override_settings(DEMO_MODE=True)
class DemoLoginTests(TestCase):
    def setUp(self):
        self.admin, self.priya = make_demo_accounts()

    def test_login_page_offers_the_demo_accounts(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:demo_login"))
        self.assertContains(response, DEMO_CUSTOMER["password"])

    def test_guests_see_the_demo_banner(self):
        self.assertContains(self.client.get(reverse("store:product_list")), "demo-strip")

    def test_one_click_customer_login(self):
        response = self.client.post(reverse("accounts:demo_login"), {"account": "customer"})
        self.assertRedirects(response, reverse("store:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.priya.pk)

    def test_one_click_admin_login_opens_the_dashboard(self):
        response = self.client.post(reverse("accounts:demo_login"), {"account": "admin"})
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.admin.pk)

    def test_unknown_account_is_not_found(self):
        response = self.client.post(reverse("accounts:demo_login"), {"account": "root"})
        self.assertEqual(response.status_code, 404)

    def test_demo_login_needs_post(self):
        self.assertEqual(self.client.get(reverse("accounts:demo_login")).status_code, 405)


@override_settings(DEMO_MODE=True)
class ReadOnlyDemoAccountTests(TestCase):
    def setUp(self):
        self.admin, self.priya = make_demo_accounts()
        self.product = make_product("Wireless Earbuds", stock=3)

    def test_dashboard_pages_still_open_and_say_read_only(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:products"))
        self.assertContains(response, "Read-only demo")
        self.assertNotContains(response, reverse("admin:index"))  # no Django admin link in the sidebar

    def test_editing_a_product_is_blocked_and_goes_back(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:product_edit", args=[self.product.pk])
        response = self.client.post(url, {"name": "Changed"}, HTTP_REFERER=f"http://testserver{url}")
        self.assertRedirects(response, f"http://testserver{url}")
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Wireless Earbuds")

    def test_delete_and_restock_are_blocked(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:product_delete", args=[self.product.pk]))
        response = self.client.post(reverse("dashboard:restock"), {"product_id": self.product.pk, "add": 50})
        self.assertRedirects(response, reverse("dashboard:index"))  # no referer: back to the overview
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)
        self.assertEqual(self.product.stock, 3)

    def test_django_admin_is_closed_to_demo_accounts(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("admin:index")), reverse("dashboard:index"))

    def test_demo_customer_cannot_change_the_profile(self):
        self.client.force_login(self.priya)
        self.client.post(reverse("accounts:profile"), PROFILE)
        self.priya.refresh_from_db()
        self.assertEqual(self.priya.first_name, "Priya")

    def test_demo_customer_can_still_shop(self):
        self.client.force_login(self.priya)
        response = self.client.post(reverse("store:api_cart_add"), {"product_id": self.product.pk, "quantity": 1},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)

    def test_other_admins_are_not_restricted(self):
        self.client.force_login(make_user("owner", role="admin"))
        self.client.post(reverse("dashboard:restock"), {"product_id": self.product.pk, "add": 50})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 53)


@override_settings(DEMO_MODE=True)
class DemoRetrainTests(TestCase):
    """Retraining stays allowed for the demo admin: it is the best part of ML Insights."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.override = override_settings(RECOMMENDER={**settings.RECOMMENDER, "ARTIFACTS_DIR": self.folder})
        self.override.enable()
        engine.reset_cache()
        category = make_category()
        for i in range(6):
            make_product(f"Phone {i}", category=category, description="android smartphone camera", slug=f"phone-{i}")
            make_product(f"Novel {i}", category=category, description="fiction story author", slug=f"novel-{i}")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.folder, ignore_errors=True)
        engine.reset_cache()

    def test_demo_admin_can_retrain(self):
        admin, _ = make_demo_accounts()
        self.client.force_login(admin)
        response = self.client.post(reverse("dashboard:retrain"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], 1)


@override_settings(DEMO_MODE=False)
class DemoModeOffTests(TestCase):
    def setUp(self):
        self.admin, self.priya = make_demo_accounts()

    def test_no_demo_logins_or_banner(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertNotContains(response, reverse("accounts:demo_login"))
        self.assertNotContains(response, "demo-strip")
        self.assertEqual(self.client.post(reverse("accounts:demo_login"), {"account": "customer"}).status_code, 404)

    def test_demo_accounts_work_normally(self):
        self.client.force_login(self.priya)
        self.client.post(reverse("accounts:profile"), PROFILE)
        self.priya.refresh_from_db()
        self.assertEqual(self.priya.first_name, "Changed")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
