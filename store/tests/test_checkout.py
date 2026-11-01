"""Checkout tests (written before the checkout service)."""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from store import services
from store.forms import CheckoutForm, luhn_valid
from store.models import Cart, CartItem, Interaction, Order

from .factories import make_category, make_product, make_user

SHIPPING = {"full_name": "Asha Rao", "phone": "9876543210", "address_line": "12 MG Road", "city": "Pune",
            "state": "Maharashtra", "pincode": "411001"}


class PaymentValidationTests(TestCase):
    def test_luhn(self):
        self.assertTrue(luhn_valid("4111 1111 1111 1111"))
        self.assertFalse(luhn_valid("4111 1111 1111 1112"))

    def form(self, **payment):
        return CheckoutForm(data={**SHIPPING, **payment})

    def test_upi_needs_a_valid_upi_id(self):
        self.assertFalse(self.form(payment_method="upi", upi_id="not-an-id").is_valid())
        self.assertTrue(self.form(payment_method="upi", upi_id="asha@okaxis").is_valid())

    def test_card_needs_valid_number_expiry_and_cvv(self):
        bad = self.form(payment_method="card", card_number="4111111111111112", card_expiry="01/20", card_cvv="1")
        self.assertFalse(bad.is_valid())
        self.assertIn("card_number", bad.errors)
        self.assertIn("card_expiry", bad.errors)
        self.assertIn("card_cvv", bad.errors)
        good = self.form(payment_method="card", card_number="4111 1111 1111 1111", card_expiry="12/35", card_cvv="123")
        self.assertTrue(good.is_valid(), good.errors)

    def test_cod_needs_no_payment_details(self):
        self.assertTrue(self.form(payment_method="cod").is_valid())

    def test_pincode_and_phone_format(self):
        form = CheckoutForm(data={**SHIPPING, "pincode": "12", "phone": "12345", "payment_method": "cod"})
        self.assertFalse(form.is_valid())
        self.assertIn("pincode", form.errors)
        self.assertIn("phone", form.errors)


class PlaceOrderTests(TestCase):
    def setUp(self):
        make_category()
        self.user = make_user()
        self.pen = make_product("Gel Pen", price="50", stock=10)
        self.lamp = make_product("Desk Lamp", price="1200", discount_price="999", stock=2)
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.pen, quantity=3)
        CartItem.objects.create(cart=self.cart, product=self.lamp, quantity=1)

    def test_order_is_created_stock_decremented_and_cart_cleared(self):
        order = services.place_order(self.user, self.cart, SHIPPING, "upi", payment_detail="asha@okaxis")

        self.assertEqual(order.subtotal, Decimal("1149"))  # 3×50 + 999
        self.assertEqual(order.shipping_fee, Decimal("0"))
        self.assertEqual(order.total, Decimal("1149"))
        self.assertEqual(order.status, Order.Status.PLACED)
        self.assertTrue(order.payment_ref.startswith("SIM-"))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.items.get(product=self.lamp).unit_price, Decimal("999"))

        self.pen.refresh_from_db()
        self.lamp.refresh_from_db()
        self.assertEqual((self.pen.stock, self.lamp.stock), (7, 1))
        self.assertFalse(self.cart.items.exists())
        self.assertEqual(Interaction.objects.filter(interaction_type="purchase").count(), 2)

    def test_card_payment_keeps_only_last_four_digits(self):
        order = services.place_order(self.user, self.cart, SHIPPING, "card", payment_detail="4111111111111111")
        self.assertIn("1111", order.payment_ref)
        self.assertNotIn("41111111", order.payment_ref)

    def test_not_enough_stock_rolls_everything_back(self):
        CartItem.objects.filter(product=self.lamp).update(quantity=5)  # only 2 in stock
        with self.assertRaises(services.OutOfStockError):
            services.place_order(self.user, self.cart, SHIPPING, "cod")
        self.assertFalse(Order.objects.exists())
        self.pen.refresh_from_db()
        self.assertEqual(self.pen.stock, 10)  # pen decrement was rolled back too
        self.assertEqual(self.cart.items.count(), 2)

    def test_empty_cart_cannot_be_ordered(self):
        self.cart.items.all().delete()
        with self.assertRaises(services.EmptyCartError):
            services.place_order(self.user, self.cart, SHIPPING, "cod")


class CheckoutViewTests(TestCase):
    def setUp(self):
        make_category()
        self.user = make_user()
        self.pen = make_product("Gel Pen", price="50", stock=10)

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("store:checkout"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('store:checkout')}")

    def test_empty_cart_redirects_to_cart(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("store:checkout")), reverse("store:cart"))

    def test_successful_checkout_redirects_to_thank_you_page(self):
        self.client.force_login(self.user)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.pen, quantity=2)
        response = self.client.post(reverse("store:checkout"), {**SHIPPING, "payment_method": "cod"})
        order = Order.objects.get()
        self.assertRedirects(response, reverse("store:order_success", args=[order.pk]))
        self.assertEqual(order.total, Decimal("149"))  # ₹100 + ₹49 shipping

    def test_order_pages_are_private(self):
        owner, stranger = self.user, make_user("stranger")
        order = Order.objects.create(user=owner, subtotal=Decimal("50"), total=Decimal("99"), payment_method="cod",
                                     **SHIPPING)
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("store:order_detail", args=[order.pk])).status_code, 404)
        self.client.force_login(owner)
        self.assertContains(self.client.get(reverse("store:order_detail", args=[order.pk])), order.order_number)
