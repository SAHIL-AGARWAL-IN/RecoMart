"""Admin dashboard: access control, analytics, CRUD, inventory, retraining and the A/B test."""
import shutil
import tempfile
from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from dashboard import analytics
from recommender import engine, services as rec_services
from recommender.models import RecommendationEvent, RecommenderSettings, TrainingRun
from store.models import Order, OrderItem, Product
from store.tests.factories import make_category, make_product, make_user

DASHBOARD_PAGES = ["dashboard:index", "dashboard:products", "dashboard:product_add", "dashboard:categories",
                   "dashboard:orders", "dashboard:inventory", "dashboard:ml_insights"]
SHIPPING = dict(full_name="Asha Rao", phone="9876543210", address_line="12 MG Road", city="Pune",
                state="Maharashtra", pincode="411001", payment_method="upi")


def make_order(user, product, quantity=1, status="placed"):
    total = product.effective_price * quantity
    order = Order.objects.create(user=user, status=status, subtotal=total, total=total, **SHIPPING)
    OrderItem.objects.create(order=order, product=product, product_name=product.name,
                             unit_price=product.effective_price, quantity=quantity)
    return order


class AccessTests(TestCase):
    def test_guests_are_sent_to_login(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_customers_are_forbidden(self):
        self.client.force_login(make_user())
        for name in DASHBOARD_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_admins_can_open_every_page(self):
        make_category()
        make_product()
        self.client.force_login(make_user("boss", role="admin"))
        for name in DASHBOARD_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class AnalyticsTests(TestCase):
    def setUp(self):
        make_category()
        self.user = make_user()
        self.pen = make_product("Pen", price="100", stock=3)
        self.lamp = make_product("Lamp", price="500", stock=50)
        make_order(self.user, self.pen, quantity=2)
        make_order(self.user, self.lamp)

    def test_kpis(self):
        kpis = analytics.kpis(days=30)
        self.assertEqual(kpis["revenue"], Decimal("700"))
        self.assertEqual(kpis["orders"], 2)
        self.assertEqual(kpis["aov"], Decimal("350"))
        self.assertEqual(kpis["customers"], 1)
        self.assertEqual(kpis["low_stock"], 1)  # the pen
        self.assertIsNone(kpis["revenue_change"])  # nothing in the previous 30 days

    def test_daily_series_covers_every_day(self):
        series = analytics.daily_sales(days=30)
        self.assertEqual(len(series), 30)
        self.assertEqual(sum(day["orders"] for day in series), 2)

    def test_top_products_by_units(self):
        top = analytics.top_products()
        self.assertEqual([(row["product_name"], row["units"]) for row in top], [("Pen", 2), ("Lamp", 1)])

    def test_ctr_by_widget(self):
        for _ in range(4):
            RecommendationEvent.objects.create(event_type="impression", widget="similar", product=self.pen)
        RecommendationEvent.objects.create(event_type="click", widget="similar", product=self.pen)
        similar = next(row for row in analytics.ctr_by_widget() if row["widget"] == "similar")
        self.assertEqual((similar["impressions"], similar["clicks"], similar["ctr_pct"]), (4, 1, 25.0))


class ZTestTests(SimpleTestCase):
    def test_big_clear_difference_is_significant(self):
        result = analytics.two_proportion_z_test(50, 1000, 100, 1000)  # 5% vs 10%
        self.assertTrue(result["significant"])
        self.assertGreater(result["z"], 3)
        self.assertEqual(result["lift"], 100.0)

    def test_tiny_difference_is_not_significant(self):
        result = analytics.two_proportion_z_test(50, 1000, 52, 1000)
        self.assertFalse(result["significant"])
        self.assertGreater(result["p_value"], 0.05)

    def test_no_data(self):
        self.assertIsNone(analytics.two_proportion_z_test(0, 0, 0, 0))


class ProductCrudTests(TestCase):
    def setUp(self):
        self.category = make_category()
        self.client.force_login(make_user("boss", role="admin"))

    def test_create_product_builds_slug(self):
        response = self.client.post(reverse("dashboard:product_add"), {
            "name": "Steel Bottle", "slug": "", "category": self.category.pk, "brand": "HomeChef",
            "description": "Keeps water cold", "price": "499", "discount_price": "", "stock": "12", "is_active": "on"})
        self.assertRedirects(response, reverse("dashboard:products"))
        self.assertEqual(Product.objects.get().slug, "steel-bottle")

    def test_discount_must_be_lower_than_price(self):
        response = self.client.post(reverse("dashboard:product_add"), {
            "name": "Bad Deal", "category": self.category.pk, "description": "x", "price": "100",
            "discount_price": "150", "stock": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.exists())

    def test_delete_unused_product(self):
        product = make_product("Unused")
        self.client.post(reverse("dashboard:product_delete", args=[product.pk]))
        self.assertFalse(Product.objects.exists())

    def test_product_in_past_orders_is_hidden_instead_of_deleted(self):
        product = make_product("Sold Before")
        make_order(make_user(), product)
        self.client.post(reverse("dashboard:product_delete", args=[product.pk]))
        product.refresh_from_db()
        self.assertFalse(product.is_active)


class OrderAndInventoryTests(TestCase):
    def setUp(self):
        make_category()
        self.product = make_product("Pen", price="50", stock=2)
        self.client.force_login(make_user("boss", role="admin"))

    def test_change_order_status(self):
        order = make_order(make_user(), self.product)
        self.client.post(reverse("dashboard:order_status", args=[order.pk]), {"status": "shipped"})
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")

    def test_order_search_by_number(self):
        order = make_order(make_user(), self.product)
        response = self.client.get(reverse("dashboard:orders"), {"q": order.order_number})
        self.assertEqual(list(response.context["object_list"]), [order])

    def test_restock_adds_units(self):
        self.client.post(reverse("dashboard:restock"), {"product_id": self.product.pk, "add": 10})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 12)

    def test_restock_never_redirects_off_site(self):
        response = self.client.post(reverse("dashboard:restock"),
                                    {"product_id": self.product.pk, "add": 1, "next": "https://evil.example/"})
        self.assertEqual(response.url, reverse("dashboard:inventory"))


class RetrainTests(TestCase):
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

    def test_retrain_requires_post_and_admin(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.post(reverse("dashboard:retrain")).status_code, 403)
        self.client.force_login(make_user("boss", role="admin"))
        self.assertEqual(self.client.get(reverse("dashboard:retrain")).status_code, 405)

    def test_retrain_trains_a_new_version(self):
        self.client.force_login(make_user("boss", role="admin"))
        data = self.client.post(reverse("dashboard:retrain")).json()
        self.assertEqual(data["version"], 1)
        self.assertEqual(TrainingRun.objects.count(), 1)
        response = self.client.get(reverse("dashboard:ml_insights"))
        self.assertContains(response, "simulated by seed_data")
        self.assertEqual(len(response.context["scatter"]), 12)


class ABTestTests(TestCase):
    def request_for(self, user=None):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.user = user or AnonymousUser()
        return request

    def test_variant_is_stable_and_splits_roughly_in_half(self):
        users = [make_user(f"shopper{i}") for i in range(200)]
        variants = [rec_services.ab_variant(self.request_for(u)) for u in users]
        self.assertEqual(variants, [rec_services.ab_variant(self.request_for(u)) for u in users])  # stable
        counts = Counter(variants)
        self.assertEqual(set(counts), {"A", "B"})
        self.assertTrue(70 <= counts["A"] <= 130, counts)

    def test_switching_the_test_off(self):
        admin = make_user("boss", role="admin")
        self.client.force_login(admin)
        self.client.post(reverse("dashboard:toggle_ab"), {})  # unchecked switch = off
        self.assertFalse(RecommenderSettings.current().ab_test_enabled)
        self.assertEqual(rec_services.ab_variant(self.request_for(admin)), "-")
        self.client.post(reverse("dashboard:toggle_ab"), {"enabled": "on"})
        self.assertTrue(RecommenderSettings.current().ab_test_enabled)

    def test_variants_use_different_rankings(self):
        self.assertEqual(rec_services.ranking_for("A"), "similarity")
        self.assertEqual(rec_services.ranking_for("B"), "hybrid")
        self.assertEqual(rec_services.ranking_for("-"), "hybrid")
