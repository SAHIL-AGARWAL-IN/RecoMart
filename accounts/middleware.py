"""Keeps the shared demo accounts read-only on the public demo. All the demo rules live here."""
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .demo import is_shared_demo_account

# Saving is blocked in the whole dashboard and on the profile page. Retraining stays allowed:
# it changes nothing a visitor typed in, and it is the best button on ML Insights.
LOCKED_NAMESPACES = {"dashboard"}
LOCKED_VIEWS = {"accounts:profile"}
ALLOWED_VIEWS = {"dashboard:retrain"}


class DemoReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Runs after the URL is matched and before the view, so it can stop the request."""
        if not is_shared_demo_account(request.user):
            return None
        match = request.resolver_match
        if match.namespace == "admin":
            # The password is public, so Django's admin site (users, passwords) stays closed.
            messages.info(request, "Django's admin site is closed on the public demo. The dashboard has everything else.")
            return redirect("dashboard:index")
        locked = match.namespace in LOCKED_NAMESPACES or match.view_name in LOCKED_VIEWS
        if request.method == "POST" and locked and match.view_name not in ALLOWED_VIEWS:
            messages.info(request, "This is a shared demo account, so saving changes is switched off. "
                                   "Everything else works.")
            return redirect(_back_url(request, match))
        return None


def _back_url(request, match):
    """The page the visitor came from, or a safe default (some blocked URLs are POST-only)."""
    referer = request.META.get("HTTP_REFERER", "")
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return referer
    return "dashboard:index" if match.namespace == "dashboard" else match.view_name
