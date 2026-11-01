"""A small, deterministic catalog: three clearly different groups of products."""
from decimal import Decimal

import pandas as pd

from store.models import Category, Product

GROUPS = {
    "Electronics": ("PhoneCo", 15000, "smartphone android camera battery display charger 5g"),
    "Books": ("Penguin", 400, "novel author chapters fiction story paperback reading"),
    "Home": ("HomeChef", 1200, "cookware pan steel kitchen nonstick frying cooking"),
}
PER_GROUP = 6


def toy_rows():
    rows, next_id = [], 1
    for category, (brand, base_price, words) in GROUPS.items():
        for i in range(PER_GROUP):
            rows.append({
                "id": next_id,
                "name": f"{category} item {i}",
                "brand": brand,
                "category": category,
                "description": f"{words} model {i}",
                "price": base_price + 50 * i,
                "rating_avg": 3.8 + 0.1 * i,
                "views": 10 + i,
                "carts": i,
                "wishlists": i % 3,
                "purchases": i % 2,
                "stock": 10,
            })
            next_id += 1
    return rows


def toy_frame():
    return pd.DataFrame(toy_rows())


def make_toy_catalog():
    """The same catalog saved in the database. Returns {category name: [products]}."""
    catalog = {}
    for name, (brand, base_price, words) in GROUPS.items():
        category = Category.objects.create(name=name, slug=name.lower())
        catalog[name] = [
            Product.objects.create(
                name=f"{name} item {i}", slug=f"{name.lower()}-item-{i}", brand=brand, category=category,
                description=f"{words} model {i}", price=Decimal(base_price + 50 * i), stock=10,
                rating_avg=Decimal("4.0"),
            )
            for i in range(PER_GROUP)
        ]
    return catalog
