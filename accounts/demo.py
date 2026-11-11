"""The shared demo accounts, and the rules for them on the public demo (settings.DEMO_MODE).

Anyone may log in as these accounts, so while DEMO_MODE is on they can look at everything
but not change the store or the account itself (see middleware.py). Visitors who want to
try more can register an account of their own.
"""
from django.conf import settings

DEMO_ADMIN = {"username": "admin", "password": "Admin@123", "first_name": "Store", "last_name": "Admin"}
DEMO_CUSTOMER = {"username": "priya", "password": "Customer@123", "first_name": "Priya", "last_name": "Sharma"}
# Keys are what the login page's one-click buttons send.
DEMO_ACCOUNTS = {"customer": DEMO_CUSTOMER, "admin": DEMO_ADMIN}
DEMO_USERNAMES = {account["username"] for account in DEMO_ACCOUNTS.values()}


def is_shared_demo_account(user):
    """True for the shared demo accounts while the site runs as a public demo."""
    return settings.DEMO_MODE and user.is_authenticated and user.username in DEMO_USERNAMES
