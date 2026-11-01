from django.test import TestCase
from django.urls import reverse

from store import services
from store.models import Interaction, Review

from .factories import make_category, make_product, make_user


class StorefrontTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.electronics = make_category("Electronics", sort_order=0)
        cls.books = make_category("Books", sort_order=1)
        cls.phone = make_product("Budget Phone", category=cls.electronics, price="9999", discount_price="7999", stock=5)
        cls.laptop = make_product("Gaming Laptop", category=cls.electronics, price="89999", stock=3)
        cls.novel = make_product("Mystery Novel", category=cls.books, price="399", stock=0)
        cls.hidden = make_product("Hidden Item", category=cls.books, price="100", is_active=False)


class HomePageTests(StorefrontTestCase):
    def test_home_page_renders_categories_in_sort_order(self):
        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([c.slug for c in response.context["categories"]], ["electronics", "books"])

    def test_deals_only_include_discounted_in_stock_products(self):
        deals = list(services.deal_products())
        self.assertEqual(deals, [self.phone])

    def test_trending_ranks_by_weighted_recent_activity(self):
        user = make_user()
        Interaction.objects.create(user=user, product=self.laptop, interaction_type="view")
        Interaction.objects.create(user=user, product=self.phone, interaction_type="purchase")
        trending = list(services.trending_products())
        self.assertEqual(trending, [self.phone, self.laptop])  # purchase (3) outweighs a view (1)


class ProductListTests(StorefrontTestCase):
    def list_names(self, url, **params):
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return [p.name for p in response.context["page"].object_list]

    def test_inactive_products_are_hidden(self):
        self.assertNotIn("Hidden Item", self.list_names(reverse("store:product_list")))

    def test_search_uses_icontains_on_name_brand_and_description(self):
        self.assertEqual(self.list_names(reverse("store:product_list"), q="LAPTOP"), ["Gaming Laptop"])

    def test_category_page_filters_by_category(self):
        names = self.list_names(reverse("store:category", args=["books"]))
        self.assertEqual(names, ["Mystery Novel"])

    def test_price_filter_uses_the_discounted_price(self):
        names = self.list_names(reverse("store:product_list"), max_price="8000")
        self.assertIn("Budget Phone", names)  # 9999 list price, but 7999 after discount
        self.assertNotIn("Gaming Laptop", names)

    def test_sort_by_price(self):
        names = self.list_names(reverse("store:product_list"), sort="price_desc")
        self.assertEqual(names, ["Gaming Laptop", "Budget Phone", "Mystery Novel"])

    def test_bad_filter_values_are_ignored(self):
        names = self.list_names(reverse("store:product_list"), min_price="abc", sort="nonsense", rating="9")
        self.assertEqual(len(names), 3)

    def test_unknown_category_is_404(self):
        self.assertEqual(self.client.get(reverse("store:category", args=["nope"])).status_code, 404)


class ProductDetailTests(StorefrontTestCase):
    def test_detail_page_shows_product_and_price(self):
        response = self.client.get(self.phone.get_absolute_url())
        self.assertContains(response, "Budget Phone")
        self.assertContains(response, "₹7,999")

    def test_viewing_logs_an_interaction_for_guests(self):
        self.client.get(self.phone.get_absolute_url())
        view = Interaction.objects.get(product=self.phone)
        self.assertEqual(view.interaction_type, Interaction.Type.VIEW)
        self.assertIsNone(view.user)
        self.assertTrue(view.session_key)

    def test_viewing_logs_the_user_when_logged_in(self):
        user = make_user()
        self.client.force_login(user)
        self.client.get(self.phone.get_absolute_url())
        self.assertEqual(Interaction.objects.get(product=self.phone).user, user)

    def test_recently_viewed_keeps_newest_first_without_duplicates(self):
        for product in (self.phone, self.laptop, self.phone):
            self.client.get(product.get_absolute_url())
        self.assertEqual(self.client.session[services.RECENTLY_VIEWED_KEY], [self.phone.id, self.laptop.id])

    def test_inactive_product_is_404(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_rating_breakdown(self):
        Review.objects.create(user=make_user("a"), product=self.phone, rating=5)
        Review.objects.create(user=make_user("b"), product=self.phone, rating=5)
        Review.objects.create(user=make_user("c"), product=self.phone, rating=2)
        breakdown = self.client.get(self.phone.get_absolute_url()).context["breakdown"]
        self.assertEqual(breakdown[0], {"stars": 5, "count": 2, "percent": 67})
        self.assertEqual(breakdown[3], {"stars": 2, "count": 1, "percent": 33})
