from decimal import Decimal

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

from store.templatetags.store_tags import indian_grouping, inr, stars


class InrFilterTests(SimpleTestCase):
    def test_indian_digit_grouping(self):
        self.assertEqual(indian_grouping("999"), "999")
        self.assertEqual(indian_grouping("1000"), "1,000")
        self.assertEqual(indian_grouping("129999"), "1,29,999")
        self.assertEqual(indian_grouping("1359999"), "13,59,999")
        self.assertEqual(indian_grouping("123456789"), "12,34,56,789")

    def test_inr_formats_rupees_and_paise(self):
        self.assertEqual(inr(Decimal("1359999.00")), "₹13,59,999")
        self.assertEqual(inr(Decimal("62.5")), "₹62.50")
        self.assertEqual(inr(0), "₹0")
        self.assertEqual(inr("not a number"), "")


class StarsTagTests(SimpleTestCase):
    def test_full_half_and_empty_stars(self):
        self.assertEqual(stars(3.5)["icons"], ["star-fill"] * 3 + ["star-half", "star"])
        self.assertEqual(stars(4.8)["icons"], ["star-fill"] * 5)
        self.assertEqual(stars(0)["icons"], ["star"] * 5)


class QueryWithTagTests(SimpleTestCase):
    def test_replaces_one_parameter_and_keeps_the_rest(self):
        request = RequestFactory().get("/products/", {"q": "phone", "sort": "rating", "page": "2"})
        html = Template("{% load store_tags %}{% query_with page=3 %}").render(Context({"request": request}))
        self.assertIn("q=phone", html)
        self.assertIn("sort=rating", html)
        self.assertIn("page=3", html)
        self.assertNotIn("page=2", html)
