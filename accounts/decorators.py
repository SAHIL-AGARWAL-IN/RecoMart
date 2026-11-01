"""Access control for the admin dashboard: only users with the admin role (or superusers) get in."""
from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def admin_required(view):
    """Function-view decorator: guests are sent to log in, logged-in customers get 403 Forbidden."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_store_admin:
            raise PermissionDenied("Store admins only.")
        return view(request, *args, **kwargs)
    return wrapper


class StoreAdminRequiredMixin(AccessMixin):
    """The same rule for class-based views (used by the dashboard CRUD pages)."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_store_admin:
            raise PermissionDenied("Store admins only.")
        return super().dispatch(request, *args, **kwargs)
