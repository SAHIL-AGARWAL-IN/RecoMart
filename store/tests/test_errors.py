from django.test import RequestFactory, TestCase
from django.views.defaults import server_error


class ErrorPageTests(TestCase):
    def test_friendly_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We couldn't find that page", status_code=404)
        self.assertContains(response, 'name="q"', status_code=404)  # offers a search box

    def test_500_page_renders_without_request_context(self):
        # Django renders 500.html with no request, user or context processors, exactly like a real crash.
        response = server_error(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Something went wrong", response.content)
