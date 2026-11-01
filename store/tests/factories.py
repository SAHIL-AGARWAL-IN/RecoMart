"""Small helpers for building test data."""
from decimal import Decimal

from django.contrib.auth import get_user_model

from store.models import Category, Product

User = get_user_model()


def make_category(name="Electronics", slug=None, **extra):
    return Category.objects.create(name=name, slug=slug or name.lower().replace(" ", "-"), **extra)


def make_product(name="Wireless Earbuds", category=None, price="1999", discount_price=None, stock=10, **extra):
    category = category or Category.objects.first() or make_category()
    return Product.objects.create(
        name=name,
        slug=extra.pop("slug", name.lower().replace(" ", "-")),
        description=extra.pop("description", f"{name} description"),
        category=category,
        price=Decimal(price),
        discount_price=Decimal(discount_price) if discount_price is not None else None,
        stock=stock,
        **extra,
    )


def make_user(username="asha", password="Testpass@123", **extra):
    return User.objects.create_user(username=username, password=password, **extra)
