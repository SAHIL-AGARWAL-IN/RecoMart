"""Training command, serving, API and click logging (uses the database)."""
import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from recommender import engine, services
from recommender.models import RecommendationData, RecommendationEvent, TrainingRun

from .fixtures import make_toy_catalog


class TrainedModelTestCase(TestCase):
    """Trains on the toy catalog into a temporary artifacts folder."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = tempfile.mkdtemp()
        cls.settings_override = override_settings(RECOMMENDER={**cls._base_settings(), "ARTIFACTS_DIR": cls.folder})
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.folder, ignore_errors=True)
        engine.reset_cache()
        super().tearDownClass()

    @staticmethod
    def _base_settings():
        from django.conf import settings
        return dict(settings.RECOMMENDER)

    def setUp(self):
        engine.reset_cache()
        self.catalog = make_toy_catalog()
        self.output = StringIO()
        call_command("train_recommender", "--k", "3", stdout=self.output)


class TrainCommandTests(TrainedModelTestCase):
    def test_command_records_run_vectors_and_neighbours(self):
        run = TrainingRun.objects.get()
        self.assertEqual((run.k, run.n_products), (3, 18))
        self.assertEqual(RecommendationData.objects.count(), 18)
        phone = self.catalog["Electronics"][0]
        phone.refresh_from_db()
        self.assertTrue(phone.feature_vector)
        text = self.output.getvalue()
        for expected in ("Dataset", "Missing values", "Feature matrix", "NaN", "silhouette", "Cluster sizes", "Saved"):
            self.assertIn(expected, text)


class SimilarProductsTests(TrainedModelTestCase):
    def test_similar_products_share_category_and_exclude_self(self):
        phone = self.catalog["Electronics"][0]
        results = services.similar_products(phone, limit=4)
        self.assertEqual(len(results), 4)
        self.assertNotIn(phone, [r.product for r in results])
        self.assertTrue(all(r.product.category.name == "Electronics" for r in results))

    def test_out_of_stock_items_go_last(self):
        phone = self.catalog["Electronics"][0]
        best = services.similar_products(phone, limit=5)[0].product
        best.stock = 0
        best.save()
        # It drops out of a short list, and comes after every in-stock product in a full list.
        self.assertNotIn(best, [r.product for r in services.similar_products(phone, limit=5)])
        everything = services.similar_products(phone, limit=17)
        self.assertEqual(everything[-1].product, best)

    def test_products_added_after_training_fall_back_to_same_category(self):
        from store.models import Product
        new_phone = Product.objects.create(name="Brand new phone", slug="brand-new-phone",
                                           category=self.catalog["Electronics"][0].category,
                                           description="new", price=999, stock=3)
        results = services.similar_products(new_phone, limit=3)
        self.assertTrue(results)
        self.assertTrue(all(r.product.category == new_phone.category for r in results))
        self.assertTrue(all(r.source == "fallback" for r in results))


class RecommendationApiTests(TrainedModelTestCase):
    def test_api_returns_json_and_logs_impressions(self):
        phone = self.catalog["Electronics"][0]
        data = self.client.get(reverse("recommender:similar", args=[phone.id])).json()
        self.assertEqual(data["product_id"], phone.id)
        self.assertEqual(data["model_version"], 1)
        self.assertEqual(len(data["results"]), 8)
        first = data["results"][0]
        for key in ("id", "name", "url", "image", "price", "rating", "in_stock", "score"):
            self.assertIn(key, first)
        self.assertIn("rec=similar", first["url"])
        self.assertEqual(RecommendationEvent.objects.filter(event_type="impression").count(), 8)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.client.get(reverse("recommender:similar", args=[99999])).status_code, 404)

    def test_opening_a_recommendation_logs_a_click_and_redirects_to_the_clean_url(self):
        phone, other = self.catalog["Electronics"][0], self.catalog["Electronics"][1]
        response = self.client.get(f"{other.get_absolute_url()}?rec=similar&src={phone.id}")
        self.assertRedirects(response, other.get_absolute_url())
        click = RecommendationEvent.objects.get(event_type="click")
        self.assertEqual((click.product, click.source_product, click.widget), (other, phone, "similar"))
