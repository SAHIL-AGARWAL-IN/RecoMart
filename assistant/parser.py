"""Read shopping filters out of a chat message with simple rules (regular expressions).

"phones under 20k, best rated" -> {"category": "electronics", "q": "phone",
                                   "max_price": 20000, "sort": "rating", ...}
The result uses the same keys as store.services.filter_products, so the assistant reuses
the store's own search instead of having a second one.
"""
import re
from decimal import Decimal

AMOUNT = r"(\d+(?:\.\d+)?)\s*(k|thousand|lakh|lac)?\b"
MULTIPLIER = {"k": 1000, "thousand": 1000, "lakh": 100000, "lac": 100000}

BETWEEN = re.compile(rf"between\s+{AMOUNT}\s+(?:and|to|-)\s+{AMOUNT}")
MAX_PRICE = re.compile(rf"(?:under|below|less than|cheaper than|up ?to|within|max(?:imum)?|not more than)\s+{AMOUNT}")
MIN_PRICE = re.compile(rf"(?:above|over|more than|at least|min(?:imum)?|starting at)\s+{AMOUNT}")
RATING = re.compile(r"(?:(\d(?:\.\d)?)\s*\+?\s*(?:stars?|★)|rated\s+(\d(?:\.\d)?)\s*\+?)")
ORDER_NUMBER = re.compile(r"\brm-?\s*0*(\d+)\b|order\s*(?:no\.?|number|#)\s*0*(\d+)", re.IGNORECASE)
SIMILAR = re.compile(r"(?:like|similar to|alternatives? (?:to|for)|same as|related to|instead of)\s+(?:the\s+|a\s+|an\s+)?(.+)$")

SORT_WORDS = [  # checked in order; the first phrase found wins
    ("price_asc", ["cheapest", "lowest price", "cheap", "budget", "affordable", "low price"]),
    ("price_desc", ["most expensive", "expensive", "premium", "highest price", "luxury"]),
    ("rating", ["best rated", "top rated", "highly rated", "best reviewed", "highest rated"]),
    ("discount", ["biggest discount", "discount", "deal", "offer", "sale"]),
    ("newest", ["newest", "latest", "new arrival"]),
    ("popular", ["popular", "best selling", "bestseller", "trending"]),
]

# Everyday words -> category. Specific product words are also kept as a search keyword
# (so "phones" narrows Electronics to phones); general words only set the category.
GENERAL_WORDS = {
    "electronics": "electronics", "gadget": "electronics", "gadgets": "electronics",
    "fashion": "fashion", "clothes": "fashion", "clothing": "fashion",
    "book": "books", "books": "books", "novel": "books", "novels": "books", "reading": "books",
    "home": "home", "kitchen": "home", "furniture": "home", "decor": "home",
    "sports": "sports", "sport": "sports", "fitness": "sports",
    "beauty": "beauty", "makeup": "beauty", "cosmetics": "beauty", "skincare": "beauty",
    "toy": "toys", "toys": "toys", "kids": "toys", "games": "toys",
    "grocery": "grocery", "groceries": "grocery", "food": "grocery",
}
SPECIFIC_WORDS = {  # word -> (category, keyword to search for)
    "phone": ("electronics", "phone"), "phones": ("electronics", "phone"), "mobile": ("electronics", "phone"),
    "mobiles": ("electronics", "phone"), "smartphone": ("electronics", "phone"), "smartphones": ("electronics", "phone"),
    "laptop": ("electronics", "laptop"), "laptops": ("electronics", "laptop"),
    "tablet": ("electronics", "tab"), "tablets": ("electronics", "tab"), "ipad": ("electronics", "ipad"),
    "earbuds": ("electronics", "earbuds"), "earphones": ("electronics", "earphone"),
    "headphones": ("electronics", "headphone"), "charger": ("electronics", "charger"),
    "speaker": ("electronics", "speaker"),
    "shirt": ("fashion", "shirt"), "shirts": ("fashion", "shirt"), "shoes": ("fashion", "shoe"),
    "sneakers": ("fashion", "shoe"), "dress": ("fashion", "dress"), "dresses": ("fashion", "dress"),
    "watch": ("fashion", "watch"), "watches": ("fashion", "watch"), "sunglasses": ("fashion", "sunglasses"),
    "handbag": ("fashion", "bag"), "handbags": ("fashion", "bag"), "bags": ("fashion", "bag"),
    "jewellery": ("fashion", "jewel"), "jewelry": ("fashion", "jewel"),
    "lipstick": ("beauty", "lipstick"), "mascara": ("beauty", "mascara"), "perfume": ("beauty", "perfume"),
    "perfumes": ("beauty", "perfume"), "fragrance": ("beauty", "perfume"),
    "sofa": ("home", "sofa"), "lamp": ("home", "lamp"), "bed": ("home", "bed"),
    "cricket": ("sports", "cricket"), "football": ("sports", "football"),
    "puzzle": ("toys", "puzzle"), "lego": ("toys", "brick"),
}
# Other words shops use for the same thing, tried when searching ("earbuds" also finds "AirPods").
SYNONYMS = {
    "earbuds": ["earbud", "airpod", "earphone", "buds"], "earphone": ["earbud", "airpod", "earphone"],
    "headphone": ["headphone", "headset", "airpods max"], "perfume": ["perfume", "fragrance", "eau de", "parfum"],
    "laptop": ["laptop", "macbook", "notebook", "zenbook", "matebook"], "shoe": ["shoe", "sneaker", "trainer"],
    "tab": ["tablet", "tab ", "ipad"], "jewel": ["jewel", "necklace", "earring", "ring"],
}
FILLER = set("""
a an the i me my we you your it is are am be do does can could would should will please show find get
give buy want need looking look for some any something anything good nice best great with and or of in on
at to from by under below above over between than less more cheap cheaper cheapest price priced rs inr
rupees rupee star stars rated rating products product items item stuff thing things which what that this
those these also only just around about maybe really very new latest top high highly low lowest one
""".split())


def _amount(number, unit):
    return Decimal(number) * MULTIPLIER.get(unit or "", 1)


def _clean(text):
    text = text.lower().replace("₹", " ")
    text = re.sub(r"(?<=\d),(?=\d)", "", text)          # 2,500 -> 2500
    text = re.sub(r"\b(?:rs\.?|inr)\s*", " ", text)      # rs. 500 -> 500
    return text


def parse_filters(text, category_slugs):
    """A filters dict for store.services.filter_products, read from a free-text message."""
    text = _clean(text)
    filters = {"q": "", "category": "", "min_price": None, "max_price": None, "rating": None, "sort": "popular"}
    used = []  # character spans already understood, left out of the keywords

    match = BETWEEN.search(text)
    if match:
        filters["min_price"], filters["max_price"] = _amount(*match.group(1, 2)), _amount(*match.group(3, 4))
        used.append(match.span())
    else:
        for pattern, key in ((MAX_PRICE, "max_price"), (MIN_PRICE, "min_price")):
            match = pattern.search(text)
            if match:
                filters[key] = _amount(match.group(1), match.group(2))
                used.append(match.span())

    match = RATING.search(text)
    if match:
        filters["rating"] = max(1, min(5, int(float(match.group(1) or match.group(2)))))
        used.append(match.span())

    for sort, phrases in SORT_WORDS:
        found = next((p for p in phrases if re.search(rf"\b{p}", text)), None)
        if found:
            filters["sort"] = sort
            used.append(re.search(rf"\b{found}\w*", text).span())
            break

    leftover = "".join(" " if any(a <= i < b for a, b in used) else ch for i, ch in enumerate(text))
    keywords = []
    for word in re.findall(r"[a-z0-9]+", leftover):
        if word in SPECIFIC_WORDS:
            category, keyword = SPECIFIC_WORDS[word]
            filters["category"] = filters["category"] or category
            keywords.append(keyword)
        elif word in GENERAL_WORDS:
            filters["category"] = filters["category"] or GENERAL_WORDS[word]
        elif word not in FILLER and not word.isdigit():
            keywords.append(word)
    if filters["category"] not in category_slugs:
        filters["category"] = ""
    filters["q"] = " ".join(keywords)
    return filters


def has_filters(filters):
    """True when the message clearly asked for a filtered search (price, rating or a product word)."""
    return any([filters["min_price"], filters["max_price"], filters["rating"], filters["category"]])


def order_number(text):
    match = ORDER_NUMBER.search(text)
    return int(match.group(1) or match.group(2)) if match else None


def similar_target(text):
    """'something like Atomic Habits' -> 'atomic habits' (the product to find similar items for)."""
    match = SIMILAR.search(text.lower().strip())
    if not match:
        return None
    return re.sub(r"[^\w\s-]", "", match.group(1)).strip() or None
