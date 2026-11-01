from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Django's built-in user plus a role that separates shoppers from store admins."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ADMIN = "admin", "Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=15, blank=True)

    @property
    def is_store_admin(self):
        """Admins get the dashboard. Superusers always count as admins."""
        return self.role == self.Role.ADMIN or self.is_superuser

    def __str__(self):
        return self.get_full_name() or self.username
