import shutil
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from recommender.models import RecommendationEvent
from store.models import Category, Interaction, Order, Product, Review
from store.seed.catalog import PER_CATEGORY, build_catalog, nice_price

User = get_user_model()


class CatalogTests(SimpleTestCase):
    def test_nice_price_ends_in_nine(self):
        self.assertEqual(nice_price(67), Decimal("69"))
        self.assertEqual(nice_price(812), Decimal("849"))
        self.assertEqual(nice_price(4321), Decimal("4299"))

    def test_catalog_has_eight_balanced_categories(self):
        catalog = build_catalog(offline=True)
        counts = {}
        for item in catalog:
            counts[item["category"]] = counts.get(item["category"], 0) + 1
        self.assertEqual(len(counts), 8)
        self.assertTrue(all(n <= PER_CATEGORY for n in counts.values()), counts)
        self.assertTrue(140 <= len(catalog) <= 160, len(catalog))

    def test_prices_are_valid(self):
        for item in build_catalog(offline=True):
            self.assertGreater(item["price"], 0)
            if item["discount_price"] is not None:
                self.assertLess(item["discount_price"], item["price"], item["name"])


class SeedCommandTests(TestCase):
    """Runs the real command offline into a temporary media folder."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_dir = tempfile.mkdtemp()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media_dir)
        cls.media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_override.disable()
        shutil.rmtree(cls.media_dir, ignore_errors=True)
        super().tearDownClass()

    def seed(self, *extra):
        call_command("seed_data", "--offline", "--users", "8", "--guests", "4", *extra, stdout=StringIO())

    def test_seed_creates_a_complete_demo_store(self):
        self.seed()
        self.assertEqual(Category.objects.count(), 8)
        self.assertGreaterEqual(Product.objects.count(), 140)

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_store_admin)
        self.assertTrue(admin.check_password("Admin@123"))
        priya = User.objects.get(username="priya")
        self.assertEqual(priya.role, User.Role.CUSTOMER)
        self.assertTrue(priya.check_password("Customer@123"))
        self.assertTrue(Interaction.objects.filter(user=priya).exists())

        # Every product has an image file on disk and a realistic rating.
        for product in Product.objects.all():
            self.assertTrue(Path(self.media_dir, product.image.name).exists(), product.image.name)
            self.assertGreaterEqual(product.rating_count, 3, product.name)
            self.assertTrue(Decimal("3.8") <= product.rating_avg <= Decimal("4.7"), (product.name, product.rating_avg))
        low_star_share = Review.objects.filter(rating__lte=2).count() / Review.objects.count()
        self.assertLess(low_star_share, 0.15)

        # About 15% of products are on a big sale (25-50% off).
        products = list(Product.objects.all())
        big_sales = [p for p in products if p.discount_percent >= 25]
        self.assertTrue(0.12 <= len(big_sales) / len(products) <= 0.25, len(big_sales))
        self.assertTrue(all(p.discount_percent <= 50 for p in products))

        # Order totals add up.
        self.assertTrue(Order.objects.exists())
        for order in Order.objects.prefetch_related("items"):
            self.assertEqual(order.subtotal, sum(i.line_total for i in order.items.all()))
            self.assertEqual(order.total, order.subtotal + order.shipping_fee)

        # Both A/B variants have simulated events.
        variants = set(RecommendationEvent.objects.filter(widget="similar").values_list("variant", flat=True))
        self.assertEqual(variants, {"A", "B"})

    def test_refuses_to_seed_twice_without_fresh(self):
        self.seed()
        with self.assertRaises(CommandError):
            self.seed()
        self.seed("--fresh")
        self.assertEqual(Category.objects.count(), 8)
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
