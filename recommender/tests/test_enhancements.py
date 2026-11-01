"""Phase 5: hybrid ranking, explanations, personalised feed, frequently bought together, recently viewed."""
import math
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from recommender import engine, explain, services
from recommender.models import RecommendationEvent
from store.models import Category, Interaction, Order, OrderItem, Product
from store.tests.factories import make_category, make_product, make_user

from .test_serving import TrainedModelTestCase


class HybridMathTests(SimpleTestCase):
    def test_recency_decays_over_90_days(self):
        self.assertEqual(engine.recency_score(0), 1.0)
        self.assertAlmostEqual(engine.recency_score(90), math.exp(-1), places=6)

    def test_hybrid_score_is_a_weighted_sum(self):
        weights = {"similarity": 0.6, "popularity": 0.25, "recency": 0.15}
        self.assertAlmostEqual(engine.hybrid_score(0.8, 0.4, 1.0, weights), 0.48 + 0.10 + 0.15)


class ExplanationTests(SimpleTestCase):
    def setUp(self):
        books = Category(name="Books", slug="books")
        self.source = Product(id=1, name="Novel A", brand="Penguin", category=books, price=Decimal("400"),
                              rating_avg=Decimal("4.0"), created_at=timezone.now() - timedelta(days=200))

    def candidate(self, **fields):
        values = dict(id=2, name="Novel B", brand="Other", category=self.source.category, price=Decimal("2000"),
                      rating_avg=Decimal("3.9"), created_at=timezone.now() - timedelta(days=200))
        values.update(fields)
        return Product(**values)

    def test_same_brand_and_similar_price(self):
        reasons = explain.similar_reasons(self.source, self.candidate(brand="Penguin", price=Decimal("450")))
        self.assertEqual(reasons, ["Same brand", "Similar price"])

    def test_at_most_two_reasons(self):
        candidate = self.candidate(brand="Penguin", price=Decimal("420"), rating_avg=Decimal("4.8"))
        self.assertEqual(len(explain.similar_reasons(self.source, candidate, co_interest=5)), 2)

    def test_shoppers_like_you_and_top_rated(self):
        reasons = explain.similar_reasons(self.source, self.candidate(rating_avg=Decimal("4.6")), co_interest=3)
        self.assertEqual(reasons, ["Popular with shoppers like you", "Top rated"])

    def test_falls_back_to_same_category(self):
        self.assertEqual(explain.similar_reasons(self.source, self.candidate()), ["Same category"])


class HybridRankingTests(TrainedModelTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_similarity_only_weights_keep_model_order(self):
        phone = self.catalog["Electronics"][0]
        weights = {"similarity": 1.0, "popularity": 0.0, "recency": 0.0}
        with override_settings(RECOMMENDER={**self._base_settings(), "ARTIFACTS_DIR": self.folder, "HYBRID_WEIGHTS": weights}):
            ranked = [s.product.id for s in services.similar_products(phone, limit=5)]
        model_order = [pid for pid, _ in engine.get_recommender().similar(phone.id, 5)]
        self.assertEqual(ranked, model_order)

    def test_popularity_can_lift_a_less_similar_product(self):
        phone = self.catalog["Electronics"][0]
        last = engine.get_recommender().similar(phone.id, 5)[-1][0]
        shopper = make_user()
        for _ in range(30):
            Interaction.objects.create(user=shopper, product_id=last, interaction_type="purchase")
        cache.clear()
        weights = {"similarity": 0.2, "popularity": 0.8, "recency": 0.0}
        with override_settings(RECOMMENDER={**self._base_settings(), "ARTIFACTS_DIR": self.folder, "HYBRID_WEIGHTS": weights}):
            self.assertEqual(services.similar_products(phone, limit=5)[0].product.id, last)

    def test_suggestions_carry_reasons(self):
        phone = self.catalog["Electronics"][0]
        for suggestion in services.similar_products(phone, limit=4):
            self.assertTrue(1 <= len(suggestion.reasons) <= 2)

    def test_shoppers_like_you_is_limited_to_the_strongest_overlaps(self):
        phone = self.catalog["Electronics"][0]
        for i in range(4):  # four shoppers looked at the phone and at every other electronics item
            shopper = make_user(f"shopper{i}")
            for product in self.catalog["Electronics"]:
                Interaction.objects.create(user=shopper, product=product, interaction_type="view")
        labelled = [s for s in services.similar_products(phone, limit=5)
                    if "Popular with shoppers like you" in s.reasons]
        self.assertLessEqual(len(labelled), services.SHOPPERS_LIKE_YOU_TOP)


class PersonalFeedTests(TrainedModelTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = make_user()
        self.books = self.catalog["Books"]
        for book in self.books[:3]:
            Interaction.objects.create(user=self.user, product=book, interaction_type="view")

    def test_feed_follows_what_the_user_browsed(self):
        mode, suggestions = services.recommended_for(self.user)
        self.assertEqual(mode, "personal")
        top = [s.product for s in suggestions[:3]]
        self.assertTrue(all(p.category.name == "Books" for p in top), top)
        self.assertTrue(all(any(r.startswith("Because you viewed") for r in s.reasons) for s in suggestions[:3]))

    def test_feed_leaves_out_purchased_products(self):
        bought = self.books[3]
        order = Order.objects.create(user=self.user, full_name="A", phone="9999999999", address_line="x", city="y",
                                     state="z", pincode="411001", payment_method="cod",
                                     subtotal=Decimal("400"), total=Decimal("449"))
        OrderItem.objects.create(order=order, product=bought, product_name=bought.name, unit_price=Decimal("400"),
                                 quantity=1)
        Interaction.objects.create(user=self.user, product=bought, interaction_type="purchase")
        _, suggestions = services.recommended_for(self.user)
        self.assertNotIn(bought, [s.product for s in suggestions])

    def test_new_users_and_guests_get_trending(self):
        mode, _ = services.recommended_for(make_user("newbie"))
        self.assertEqual(mode, "trending")
        data = self.client.get(reverse("recommender:for_you")).json()
        self.assertEqual(data["mode"], "trending")

    def test_api_returns_personal_feed_and_logs_impressions(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("recommender:for_you")).json()
        self.assertEqual(data["mode"], "personal")
        self.assertTrue(data["results"][0]["reasons"])
        self.assertIn("rec=for_you", data["results"][0]["url"])
        self.assertTrue(RecommendationEvent.objects.filter(widget="for_you", event_type="impression").exists())


class FrequentlyBoughtTogetherTests(TestCase):
    def setUp(self):
        cache.clear()
        make_category()
        self.pen = make_product("Pen", price="50", stock=50)
        self.ink = make_product("Ink", price="80", stock=50)
        self.pad = make_product("Notepad", price="120", stock=50)
        self.user = make_user()
        for basket in ([self.pen, self.ink], [self.pen, self.ink], [self.pen, self.pad], [self.ink, self.pad]):
            order = Order.objects.create(user=self.user, full_name="A", phone="9999999999", address_line="x",
                                         city="y", state="z", pincode="411001", payment_method="cod",
                                         subtotal=Decimal("100"), total=Decimal("149"))
            for product in basket:
                OrderItem.objects.create(order=order, product=product, product_name=product.name,
                                         unit_price=product.price, quantity=1)

    def test_counts_orders_that_contain_both(self):
        results = services.frequently_bought_together([self.pen.id])
        self.assertEqual([(s.product, s.together) for s in results], [(self.ink, 2), (self.pad, 1)])
        self.assertEqual(results[0].reasons, ["Bought together ×2"])

    def test_items_already_in_the_cart_are_left_out(self):
        products = [s.product for s in services.frequently_bought_together([self.pen.id, self.ink.id])]
        self.assertEqual(products, [self.pad])

    def test_api_uses_the_current_cart(self):
        self.client.post(reverse("store:api_cart_add"), {"product_id": self.pen.id}, content_type="application/json")
        data = self.client.get(reverse("recommender:frequently_bought")).json()
        self.assertEqual(data["results"][0]["name"], "Ink")
        self.assertIn("rec=fbt", data["results"][0]["url"])


class RecentlyViewedTests(TestCase):
    def setUp(self):
        category = make_category()
        self.first = make_product("First Thing", category=category)
        self.second = make_product("Second Thing", category=category)

    def test_home_shows_recently_viewed_products(self):
        self.assertNotContains(self.client.get(reverse("store:home")), "Recently viewed")
        self.client.get(self.first.get_absolute_url())
        self.client.get(self.second.get_absolute_url())
        response = self.client.get(reverse("store:home"))
        self.assertContains(response, "Recently viewed")
        self.assertEqual(response.context["recently_viewed"], [self.second, self.first])

    def test_product_page_leaves_out_the_current_product(self):
        self.client.get(self.first.get_absolute_url())
        response = self.client.get(self.second.get_absolute_url())
        self.assertEqual(response.context["recently_viewed"], [self.first])
