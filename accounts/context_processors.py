from django.conf import settings

from .demo import DEMO_ACCOUNTS, is_shared_demo_account


def demo(request):
    """Lets every template show the demo banner, the demo logins and the read-only notice."""
    user = getattr(request, "user", None)
    return {
        "demo_mode": settings.DEMO_MODE,
        "demo_accounts": DEMO_ACCOUNTS if settings.DEMO_MODE else {},
        "shared_demo_account": bool(user) and is_shared_demo_account(user),
    }
