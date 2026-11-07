"""Guard against N+1 queries: list pages must not make one extra query per item shown."""
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from store.models import Order, OrderItem

from .factories import make_category, make_product, make_user

SHIPPING = dict(full_name="A", phone="9999999999", address_line="x", city="y", state="z", pincode="411001",
                payment_method="cod")


class QueryCountTests(TestCase):
    def setUp(self):
        self.category = make_category()
        self.user = make_user("shopper")
        self.admin = make_user("boss", role="admin")
        self.made = 0

    def add_products(self, n):
        for _ in range(n):
            self.made += 1
            product = make_product(f"Item {self.made}", category=self.category, slug=f"item-{self.made}")
            order = Order.objects.create(user=self.user, subtotal=Decimal("10"), total=Decimal("10"), **SHIPPING)
            OrderItem.objects.create(order=order, product=product, product_name=product.name,
                                     unit_price=product.price, quantity=1)

    def queries_for(self, client, url):
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(client.get(url).status_code, 200)
        return len(ctx.captured_queries)

    def assert_constant(self, client, url):
        self.add_products(3)
        few = self.queries_for(client, url)
        self.add_products(12)
        many = self.queries_for(client, url)
        self.assertEqual(few, many, f"{url}: {few} queries with 3 items but {many} with 15 (N+1?)")

    def test_product_list(self):
        self.assert_constant(self.client, reverse("store:product_list"))

    def test_order_history(self):
        self.client.force_login(self.user)
        self.assert_constant(self.client, reverse("store:order_list"))

    def test_dashboard_product_and_order_lists(self):
        self.client.force_login(self.admin)
        self.assert_constant(self.client, reverse("dashboard:products"))
        self.assert_constant(self.client, reverse("dashboard:orders"))
