"""The /api/assistant/ endpoint end to end (uses the database)."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from store.models import Cart, CartItem, Order
from store.tests.factories import make_category, make_product, make_user

SHIPPING = dict(full_name="Asha Rao", phone="9876543210", address_line="12 MG Road", city="Pune",
                state="Maharashtra", pincode="411001", payment_method="upi")


class AssistantApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        electronics = make_category("Electronics", slug="electronics")
        books = make_category("Books", slug="books")
        self.cheap_phone = make_product("Budget Smartphone", category=electronics, price="9999",
                                        description="android smartphone with camera")
        self.pricey_phone = make_product("Flagship Smartphone", category=electronics, price="79999",
                                         description="premium android smartphone")
        self.novel = make_product("Mystery Novel", category=books, price="399", description="a gripping fiction story")

    def ask(self, message):
        return self.client.post(reverse("assistant:reply"), {"message": message}, content_type="application/json")


class SearchAndAnswerTests(AssistantApiTestCase):
    def test_search_applies_price_filter(self):
        data = self.ask("phones under 20000").json()
        self.assertEqual(data["intent"], "search")
        self.assertEqual([p["name"] for p in data["products"]], ["Budget Smartphone"])
        self.assertIn("/products/?", data["link"]["url"])

    def test_follow_up_chips_carry_the_whole_question(self):
        make_product("Value Smartphone", category=self.cheap_phone.category, price="12999",
                     description="android smartphone")  # two results, so sort chips are offered
        chips = self.ask("phones under 20000 cheapest").json()["chips"]
        best = next(c for c in chips if c["label"] == "Best rated")
        self.assertEqual(best["message"], "phones under 20000 best rated")  # old sort word replaced
        data = self.ask(best["message"]).json()
        self.assertEqual(data["intent"], "search")

    def test_similar_uses_the_recommender_fallback(self):
        data = self.ask("something like Budget Smartphone").json()
        self.assertEqual(data["intent"], "similar")
        self.assertIn("Flagship Smartphone", [p["name"] for p in data["products"]])
        self.assertNotIn("Budget Smartphone", [p["name"] for p in data["products"]])

    def test_faq_mentions_free_delivery_threshold(self):
        data = self.ask("how much is delivery").json()
        self.assertEqual(data["intent"], "faq_delivery")
        self.assertIn("₹499", data["text"])

    def test_greeting_offers_quick_replies(self):
        data = self.ask("hello").json()
        self.assertTrue(data["chips"])

    def test_unknown_message_gets_a_polite_fallback(self):
        data = self.ask("qwzx plmok vbnr").json()
        self.assertEqual(data["intent"], "fallback")
        self.assertTrue(data["chips"])


class PrivateDataTests(AssistantApiTestCase):
    def test_guests_are_asked_to_log_in_for_orders(self):
        data = self.ask("where is my order").json()
        self.assertEqual(data["intent"], "order_status")
        self.assertIn("log in", data["text"].lower())
        self.assertIn("/accounts/login/", data["link"]["url"])

    def test_shows_your_latest_order(self):
        me = make_user("me")
        order = Order.objects.create(user=me, status="shipped", subtotal=Decimal("399"), total=Decimal("448"), **SHIPPING)
        self.client.force_login(me)
        data = self.ask("where is my order").json()
        self.assertIn(order.order_number, data["text"])
        self.assertIn("shipped", data["text"].lower())

    def test_never_shows_someone_elses_order(self):
        other = make_user("other")
        theirs = Order.objects.create(user=other, subtotal=Decimal("399"), total=Decimal("448"), **SHIPPING)
        self.client.force_login(make_user("me"))
        data = self.ask(f"status of {theirs.order_number}").json()
        self.assertNotIn("Asha", data["text"])
        self.assertIn("couldn't find", data["text"].lower())

    def test_cart_summary(self):
        cart = Cart.objects.create(session_key="x")
        session = self.client.session
        session["cart_id"] = cart.id
        session.save()
        CartItem.objects.create(cart=cart, product=self.novel, quantity=2)
        data = self.ask("what's in my cart").json()
        self.assertEqual(data["intent"], "cart")
        self.assertIn("2 items", data["text"])
        self.assertIn("₹798", data["text"])


class PlacementTests(AssistantApiTestCase):
    def test_chat_is_on_shop_pages_but_not_in_the_admin_dashboard(self):
        self.assertContains(self.client.get(reverse("store:home")), "data-assistant")
        self.client.force_login(make_user("boss", role="admin"))
        self.assertNotContains(self.client.get(reverse("dashboard:index")), "data-assistant")

    def test_product_page_tells_the_chat_which_product_is_open(self):
        response = self.client.get(self.novel.get_absolute_url())
        self.assertContains(response, f'data-current-product="{self.novel.id}"')


class GuardrailTests(AssistantApiTestCase):
    def test_only_post(self):
        self.assertEqual(self.client.get(reverse("assistant:reply")).status_code, 405)

    def test_empty_or_too_long_messages_are_rejected(self):
        self.assertEqual(self.ask("").status_code, 400)
        self.assertEqual(self.ask("x" * 501).status_code, 400)

    def test_rate_limit_per_session(self):
        for _ in range(20):
            self.assertEqual(self.ask("hi").status_code, 200)
        self.assertEqual(self.ask("hi").status_code, 429)
