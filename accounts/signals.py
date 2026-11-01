from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from store.cart import merge_session_cart_on_login


@receiver(user_logged_in)
def move_guest_cart_to_account(sender, request, user, **kwargs):
    """Items a guest put in their cart are kept when they log in."""
    if request is not None:
        merge_session_cart_on_login(request, user)
