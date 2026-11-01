from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from store.models import Cart, CartItem, Order, Review
from store.services import shipping_fee_for

from .factories import make_category, make_product, make_user


class ProductTests(TestCase):
    def setUp(self):
        self.category = make_category()

    def test_effective_price_uses_discount_when_present(self):
        product = make_product(price="1000", discount_price="750")
        self.assertEqual(product.effective_price, Decimal("750"))
        self.assertEqual(product.discount_percent, 25)

    def test_effective_price_without_discount(self):
        product = make_product(price="1000")
        self.assertEqual(product.effective_price, Decimal("1000"))
        self.assertEqual(product.discount_percent, 0)

    def test_discount_must_be_lower_than_price(self):
        product = make_product(price="1000", discount_price="1200")
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_in_stock(self):
        self.assertTrue(make_product(name="A", stock=3).in_stock)
        self.assertFalse(make_product(name="B", stock=0).in_stock)


class ReviewRatingTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.asha = make_user("asha")
        self.vikram = make_user("vikram")

    def test_saving_reviews_updates_product_rating(self):
        Review.objects.create(user=self.asha, product=self.product, rating=5)
        Review.objects.create(user=self.vikram, product=self.product, rating=2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_avg, Decimal("3.50"))
        self.assertEqual(self.product.rating_count, 2)

    def test_deleting_a_review_updates_product_rating(self):
        review = Review.objects.create(user=self.asha, product=self.product, rating=1)
        Review.objects.create(user=self.vikram, product=self.product, rating=5)
        review.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_avg, Decimal("5.00"))
        self.assertEqual(self.product.rating_count, 1)

    def test_one_review_per_user_per_product(self):
        Review.objects.create(user=self.asha, product=self.product, rating=4)
        with self.assertRaises(IntegrityError):
            Review.objects.create(user=self.asha, product=self.product, rating=3)


class CartModelTests(TestCase):
    def test_subtotal_and_quantity(self):
        cart = Cart.objects.create(session_key="guest123")
        CartItem.objects.create(cart=cart, product=make_product(name="Pen", price="50"), quantity=3)
        CartItem.objects.create(cart=cart, product=make_product(name="Book", price="400", discount_price="300"))
        self.assertEqual(cart.total_quantity, 4)
        self.assertEqual(cart.subtotal, Decimal("450"))


class OrderTests(TestCase):
    def test_order_number_format(self):
        order = Order.objects.create(
            user=make_user(), full_name="Asha Rao", phone="9876543210", address_line="12 MG Road",
            city="Pune", state="Maharashtra", pincode="411001", payment_method=Order.PaymentMethod.UPI,
            subtotal=Decimal("500"), total=Decimal("500"),
        )
        self.assertEqual(order.order_number, f"RM-{order.pk:06d}")
        self.assertEqual(order.status, Order.Status.PLACED)

    def test_shipping_is_free_from_499(self):
        self.assertEqual(shipping_fee_for(Decimal("499")), Decimal("0"))
        self.assertEqual(shipping_fee_for(Decimal("498")), Decimal("49"))
