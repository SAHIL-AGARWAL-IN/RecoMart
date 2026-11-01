"""Tests for the wishlist, review, search and product-filter endpoints."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from store.models import Interaction, Order, OrderItem, Review, WishlistItem

from .factories import make_category, make_product, make_user


class WishlistApiTests(TestCase):
    def setUp(self):
        make_category()
        self.phone = make_product("Budget Phone", price="9999")
        self.url = reverse("store:api_wishlist_toggle", args=[self.phone.id])

    def test_guests_get_401_with_a_login_link(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertIn(reverse("accounts:login"), response.json()["login_url"])

    def test_toggle_adds_then_removes(self):
        user = make_user()
        self.client.force_login(user)
        data = self.client.post(self.url).json()
        self.assertEqual((data["wishlisted"], data["count"]), (True, 1))
        self.assertTrue(Interaction.objects.filter(product=self.phone, interaction_type="wishlist").exists())
        data = self.client.post(self.url).json()
        self.assertEqual((data["wishlisted"], data["count"]), (False, 0))
        self.assertFalse(WishlistItem.objects.exists())

    def test_heart_shows_saved_state_on_cards(self):
        user = make_user()
        WishlistItem.objects.create(user=user, product=self.phone)
        self.client.force_login(user)
        response = self.client.get(reverse("store:product_list"))
        self.assertContains(response, 'aria-pressed="true"')


class ReviewTests(TestCase):
    def setUp(self):
        make_category()
        self.phone = make_product("Budget Phone", price="9999")
        self.url = reverse("store:submit_review", args=[self.phone.slug])
        self.user = make_user()

    def test_review_requires_login(self):
        response = self.client.post(self.url, {"rating": 5})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Review.objects.exists())

    def test_posting_twice_updates_the_same_review(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"rating": 2, "comment": "Meh"})
        self.client.post(self.url, {"rating": 5, "comment": "Grew on me"})
        review = Review.objects.get()
        self.assertEqual((review.rating, review.comment), (5, "Grew on me"))
        self.phone.refresh_from_db()
        self.assertEqual(self.phone.rating_avg, Decimal("5.00"))
        self.assertEqual(Interaction.objects.filter(interaction_type="review").count(), 1)

    def test_invalid_rating_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"rating": 9})
        self.assertFalse(Review.objects.exists())

    def test_verified_purchase_badge(self):
        order = Order.objects.create(user=self.user, full_name="A", phone="9999999999", address_line="x", city="y",
                                     state="z", pincode="411001", payment_method="cod",
                                     subtotal=Decimal("9999"), total=Decimal("9999"))
        OrderItem.objects.create(order=order, product=self.phone, product_name="Budget Phone",
                                 unit_price=Decimal("9999"), quantity=1)
        Review.objects.create(user=self.user, product=self.phone, rating=4)
        self.assertContains(self.client.get(self.phone.get_absolute_url()), "Verified purchase")


class SearchApiTests(TestCase):
    def setUp(self):
        category = make_category()
        for i in range(8):
            make_product(f"Phone Model {i}", category=category, slug=f"phone-{i}")
        make_product("Desk Lamp", category=category)

    def test_short_queries_return_nothing(self):
        data = self.client.get(reverse("store:api_search"), {"q": "p"}).json()
        self.assertEqual(data["results"], [])

    def test_results_are_limited_with_a_total_and_see_all_link(self):
        data = self.client.get(reverse("store:api_search"), {"q": "phone"}).json()
        self.assertEqual(len(data["results"]), 6)
        self.assertEqual(data["total"], 8)
        self.assertEqual(set(data["results"][0]), {"name", "brand", "category", "price", "image", "url"})
        self.assertIn("q=phone", data["see_all_url"])

    def test_name_matches_rank_above_description_matches(self):
        make_product("Leather Wallet", description="Fits a phone and cards", slug="wallet")
        names = [r["name"] for r in self.client.get(reverse("store:api_search"), {"q": "phone"}).json()["results"]]
        self.assertNotIn("Leather Wallet", names)  # 8 name matches fill the 6 slots first


class ProductsApiTests(TestCase):
    def setUp(self):
        electronics = make_category("Electronics")
        books = make_category("Books")
        make_product("Budget Phone", category=electronics, price="9999")
        make_product("Mystery Novel", category=books, price="399")

    def test_returns_rendered_grid_html(self):
        data = self.client.get(reverse("store:api_products"), {"max_price": "1000"}).json()
        self.assertEqual(data["count"], 1)
        self.assertIn("Mystery Novel", data["html"])
        self.assertNotIn("Budget Phone", data["html"])

    def test_category_parameter(self):
        data = self.client.get(reverse("store:api_products"), {"category": "electronics"}).json()
        self.assertEqual(data["count"], 1)
        self.assertIn("Budget Phone", data["html"])
