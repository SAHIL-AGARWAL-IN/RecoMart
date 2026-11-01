"""Build the seed catalog from the DummyJSON snapshot plus our hand-written books and toys.

`dummyjson_products.json` is a committed copy of https://dummyjson.com/products?limit=0,
so every teammate seeds the same catalog. Only the product photos are downloaded.
"""
import json
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .books_toys import BOOKS, TOYS

SNAPSHOT_PATH = Path(__file__).with_name("dummyjson_products.json")
DUMMYJSON_URL = "https://dummyjson.com/products?limit=0"
USD_TO_INR = 85
PER_CATEGORY = 22
MIN_DISCOUNT_PERCENT = 8  # smaller DummyJSON discounts are ignored, so some items sell at full price

# Our 8 store categories. `icon` is a Bootstrap Icons name.
CATEGORIES = [
    {"name": "Electronics", "slug": "electronics", "icon": "laptop",
     "description": "Phones, laptops, tablets and accessories"},
    {"name": "Fashion", "slug": "fashion", "icon": "handbag",
     "description": "Clothing, shoes, watches, bags and jewellery"},
    {"name": "Books", "slug": "books", "icon": "book",
     "description": "Bestsellers, fiction, self-help and programming"},
    {"name": "Home & Kitchen", "slug": "home", "icon": "lamp",
     "description": "Furniture, decor and kitchen essentials"},
    {"name": "Sports", "slug": "sports", "icon": "bicycle",
     "description": "Sports gear and fitness accessories"},
    {"name": "Beauty", "slug": "beauty", "icon": "stars",
     "description": "Makeup, fragrances and skin care"},
    {"name": "Toys", "slug": "toys", "icon": "puzzle",
     "description": "Building sets, RC cars, puzzles and STEM kits"},
    {"name": "Grocery", "slug": "grocery", "icon": "basket",
     "description": "Fresh produce, staples and daily needs"},
]

# DummyJSON category -> our category slug. Vehicles and motorcycles are left out.
CATEGORY_MAP = {
    "smartphones": "electronics", "laptops": "electronics", "tablets": "electronics",
    "mobile-accessories": "electronics",
    "mens-shirts": "fashion", "mens-shoes": "fashion", "mens-watches": "fashion", "tops": "fashion",
    "womens-dresses": "fashion", "womens-shoes": "fashion", "womens-bags": "fashion",
    "womens-jewellery": "fashion", "womens-watches": "fashion", "sunglasses": "fashion",
    "beauty": "beauty", "fragrances": "beauty", "skin-care": "beauty",
    "furniture": "home", "home-decoration": "home", "kitchen-accessories": "home",
    "sports-accessories": "sports",
    "groceries": "grocery",
}

# Some DummyJSON products have no brand; give them a believable house brand.
HOUSE_BRANDS = {
    "groceries": "RecoMart Fresh",
    "kitchen-accessories": "HomeChef",
    "home-decoration": "Casa Decor",
}


def nice_price(inr):
    """Round to a shop-style price that ends in 9: 67 -> 69, 812 -> 849, 4321 -> 4299."""
    inr = float(inr)
    if inr < 100:
        value = max(9, math.ceil(inr / 10) * 10 - 1)
    elif inr < 1000:
        value = math.ceil(inr / 50) * 50 - 1
    else:
        value = round(inr / 100) * 100 - 1
    return Decimal(value)


def nice_price_down(inr, step):
    """Round down to a price ending in 9 at the given step: (263, 50) -> 249, (4321, 100) -> 4299."""
    return Decimal(math.floor(float(inr) / step) * step - 1)


def discounted_price(price, percent):
    """Sale price after `percent` off, rounded down to a shop-style price, or None if no real discount.

    Tries coarse steps first (₹..99), then finer ones (₹..49, ₹..9), and keeps the first one that
    moves the price by at most 5% of the original, so the advertised discount stays honest.
    """
    exact = price * Decimal(1 - percent / 100)
    candidate = exact.quantize(Decimal("1"))
    for step in (100, 50, 10):
        rounded = nice_price_down(exact, step)
        if rounded > 0 and exact - rounded <= price * Decimal("0.05"):
            candidate = rounded
            break
    return candidate if candidate < price else None


def load_snapshot(offline=False):
    """Read the committed DummyJSON snapshot, downloading it only if it is missing."""
    if not SNAPSHOT_PATH.exists():
        if offline:
            raise FileNotFoundError(f"{SNAPSHOT_PATH.name} is missing and --offline was given.")
        import requests

        response = requests.get(DUMMYJSON_URL, timeout=30)
        response.raise_for_status()
        SNAPSHOT_PATH.write_text(response.text, encoding="utf-8")
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))["products"]


def _round_robin(items_by_sub, limit):
    """Pick items alternately from each sub-category, so fashion gets shoes AND watches AND bags."""
    picked, queues = [], [list(items) for items in items_by_sub.values()]
    while len(picked) < limit and any(queues):
        for queue in queues:
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return picked


def _from_dummyjson(raw):
    category = CATEGORY_MAP[raw["category"]]
    price = nice_price(raw["price"] * USD_TO_INR)
    discount_price = None
    if raw.get("discountPercentage", 0) >= MIN_DISCOUNT_PERCENT:
        discount_price = discounted_price(price, raw["discountPercentage"])
    return {
        "name": raw["title"],
        "brand": raw.get("brand") or HOUSE_BRANDS.get(raw["category"], "RecoMart Basics"),
        "description": raw["description"],
        "category": category,
        "price": price,
        "discount_price": discount_price,
        "stock": int(raw.get("stock", 0)),
        "base_rating": float(raw.get("rating", 4.0)),
        "image_urls": raw.get("images") or [raw["thumbnail"]],
        "image_kind": "photo",
    }


def _from_hand_written(rows, category, kind):
    products = []
    for name, brand, description, price, discount, stock, rating in rows:
        price = Decimal(price)
        products.append({
            "name": name,
            "brand": brand,
            "description": description,
            "category": category,
            "price": price,
            "discount_price": discounted_price(price, discount) if discount else None,
            "stock": stock,
            "base_rating": rating,
            "image_urls": [],
            "image_kind": kind,  # "book" or "toy": the image is drawn with Pillow
        })
    return products


def build_catalog(offline=False):
    """Return a list of product dicts ready to be saved, about 150 in total."""
    by_category = defaultdict(lambda: defaultdict(list))
    for raw in sorted(load_snapshot(offline), key=lambda p: p["id"]):
        if raw["category"] in CATEGORY_MAP:
            by_category[CATEGORY_MAP[raw["category"]]][raw["category"]].append(raw)

    catalog = []
    for category_slug, subcategories in by_category.items():
        catalog += [_from_dummyjson(raw) for raw in _round_robin(subcategories, PER_CATEGORY)]
    catalog += _from_hand_written(BOOKS, "books", "book")
    catalog += _from_hand_written(TOYS, "toys", "toy")
    return catalog
