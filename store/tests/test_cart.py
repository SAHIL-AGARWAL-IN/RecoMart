"""Cart service tests (written before store/cart.py was extended)."""
from decimal import Decimal

from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from store import cart as cart_service
from store.models import Cart, CartItem, Interaction

from .factories import make_category, make_product, make_user


def guest_request():
    request = RequestFactory().get("/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request.user = AnonymousUser()
    return request


class CartServiceTests(TestCase):
    def setUp(self):
        make_category()
        self.pen = make_product("Gel Pen", price="50", stock=10)
        self.lamp = make_product("Desk Lamp", price="1200", discount_price="999", stock=2)

    def test_guest_gets_a_cart_remembered_in_the_session(self):
        request = guest_request()
        cart = cart_service.get_or_create_cart(request)
        self.assertIsNone(cart.user)
        self.assertEqual(request.session[cart_service.CART_SESSION_KEY], cart.id)
        self.assertEqual(cart_service.get_cart(request), cart)

    def test_logged_in_user_gets_their_own_cart(self):
        request = guest_request()
        request.user = make_user()
        cart = cart_service.get_or_create_cart(request)
        self.assertEqual(cart.user, request.user)

    def test_add_item_twice_increases_quantity(self):
        cart = Cart.objects.create()
        cart_service.add_item(cart, self.pen, 2)
        cart_service.add_item(cart, self.pen, 3)
        self.assertEqual(cart.items.get(product=self.pen).quantity, 5)

    def test_quantity_is_capped_at_stock(self):
        cart = Cart.objects.create()
        item, capped = cart_service.add_item(cart, self.lamp, 5)
        self.assertEqual(item.quantity, 2)
        self.assertTrue(capped)

    def test_cannot_add_out_of_stock_or_inactive_products(self):
        cart = Cart.objects.create()
        sold_out = make_product("Sold Out", stock=0)
        hidden = make_product("Hidden", stock=5, is_active=False)
        for product in (sold_out, hidden):
            with self.assertRaises(cart_service.CartError):
                cart_service.add_item(cart, product)

    def test_set_quantity_and_remove(self):
        cart = Cart.objects.create()
        cart_service.add_item(cart, self.pen, 1)
        cart_service.set_quantity(cart, self.pen.id, 4)
        self.assertEqual(cart.items.get(product=self.pen).quantity, 4)
        cart_service.set_quantity(cart, self.pen.id, 0)  # 0 means remove
        self.assertFalse(cart.items.exists())

    def test_summary_adds_shipping_below_free_threshold(self):
        cart = Cart.objects.create()
        cart_service.add_item(cart, self.pen, 2)  # ₹100
        summary = cart_service.summary(cart)
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["subtotal"], Decimal("100"))
        self.assertEqual(summary["shipping"], Decimal("49"))
        self.assertEqual(summary["total"], Decimal("149"))
        self.assertEqual(summary["free_shipping_remaining"], Decimal("399"))

        cart_service.add_item(cart, self.lamp, 1)  # +₹999 → free shipping
        summary = cart_service.summary(cart)
        self.assertEqual(summary["shipping"], Decimal("0"))
        self.assertEqual(summary["free_shipping_remaining"], Decimal("0"))

    def test_merge_guest_cart_into_user_cart(self):
        user = make_user()
        user_cart = Cart.objects.create(user=user)
        cart_service.add_item(user_cart, self.lamp, 1)
        guest_cart = Cart.objects.create(session_key="guest")
        cart_service.add_item(guest_cart, self.lamp, 2)
        cart_service.add_item(guest_cart, self.pen, 3)

        cart_service.merge_carts(guest_cart, user_cart)

        self.assertFalse(Cart.objects.filter(pk=guest_cart.pk).exists())
        quantities = dict(user_cart.items.values_list("product__name", "quantity"))
        self.assertEqual(quantities, {"Desk Lamp": 2, "Gel Pen": 3})  # lamp capped at stock 2


class CartMergeOnLoginTests(TestCase):
    def test_guest_cart_moves_to_the_account_after_login(self):
        make_category()
        pen = make_product("Gel Pen", price="50", stock=10)
        make_user("asha", password="Shopping@2026")

        self.client.post(reverse("store:api_cart_add"), {"product_id": pen.id, "quantity": 2},
                         content_type="application/json")
        self.client.post(reverse("accounts:login"), {"username": "asha", "password": "Shopping@2026"})

        cart = Cart.objects.get(user__username="asha")
        self.assertEqual(cart.items.get().quantity, 2)
        self.assertEqual(Cart.objects.count(), 1)


class CartApiTests(TestCase):
    def setUp(self):
        make_category()
        self.pen = make_product("Gel Pen", price="50", stock=10)

    def post(self, name, data):
        return self.client.post(reverse(name), data, content_type="application/json")

    def test_add_returns_badge_count_and_logs_interaction(self):
        response = self.post("store:api_cart_add", {"product_id": self.pen.id, "quantity": 3})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["cart"]["count"], 3)
        self.assertIn("added", data["message"].lower())
        self.assertTrue(Interaction.objects.filter(product=self.pen, interaction_type="cart").exists())

    def test_update_and_remove(self):
        self.post("store:api_cart_add", {"product_id": self.pen.id, "quantity": 1})
        data = self.post("store:api_cart_update", {"product_id": self.pen.id, "quantity": 4}).json()
        self.assertEqual(data["item"]["quantity"], 4)
        self.assertEqual(data["item"]["line_total"], "₹200")
        data = self.post("store:api_cart_remove", {"product_id": self.pen.id}).json()
        self.assertEqual(data["cart"]["count"], 0)
        self.assertFalse(CartItem.objects.exists())

    def test_errors_return_400_json(self):
        response = self.post("store:api_cart_add", {"product_id": 99999})
        self.assertEqual(response.status_code, 404)
        sold_out = make_product("Sold Out", stock=0)
        response = self.post("store:api_cart_add", {"product_id": sold_out.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse("store:api_cart_add")).status_code, 405)
