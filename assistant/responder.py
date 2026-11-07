"""Turn an intent into a reply: short text, optional product cards, quick-reply chips and a link.

Every answer comes from the store's own services (search, recommender, cart, orders),
so the assistant never shows anything the website itself wouldn't.
"""
from functools import reduce
from operator import and_
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from recommender import services as rec_services
from store import cart as cart_service
from store import services as store_services
from store.models import Category, Order, Product
from store.templatetags.store_tags import inr

from . import parser

MAX_CARDS = 6
PRODUCT_MATCH_THRESHOLD = 0.3

START_CHIPS = ["Phones under ₹20,000", "Something like Atomic Habits", "Recommend something for me",
               "Where is my order?", "What's in my cart?", "Delivery charges"]


def reply(text, products=(), chips=(), link=None):
    return {"text": text, "products": list(products), "chips": list(chips), "link": link}


def _link(label, url):
    return {"label": label, "url": url}


# --------------------------------------------------------------------- search
def _matches(word):
    """A product mentions this word, or one of its synonyms, in its name, brand or description."""
    q = Q()
    for term in parser.SYNONYMS.get(word, [word]):
        q |= Q(name__icontains=term) | Q(brand__icontains=term) | Q(description__icontains=term)
    return q


def _keyword_search(filters, words=None):
    """Store search where every keyword must match (AND), so 'red lipstick' needs both words."""
    words = filters["q"].split() if words is None else words
    products = store_services.filter_products({**filters, "q": ""})
    if words:
        products = products.filter(reduce(and_, [_matches(w) for w in words]))
    return products


def _filters_url(filters):
    params = {key: value for key, value in filters.items() if value not in (None, "", "popular")}
    return f"{reverse('store:product_list')}?{urlencode(params)}"


def _describe(filters, count):
    parts = []
    if filters["q"]:
        parts.append(f"“{filters['q']}”")
    if filters["category"]:
        parts.append(f"in {Category.objects.filter(slug=filters['category']).values_list('name', flat=True).first()}")
    if filters["max_price"] and filters["min_price"]:
        parts.append(f"between {inr(filters['min_price'])} and {inr(filters['max_price'])}")
    elif filters["max_price"]:
        parts.append(f"under {inr(filters['max_price'])}")
    elif filters["min_price"]:
        parts.append(f"above {inr(filters['min_price'])}")
    if filters["rating"]:
        parts.append(f"rated {filters['rating']}+ stars")
    what = " ".join(parts) or "for you"
    return f"I found {count} product{'s' if count != 1 else ''} {what}."


def search(text, request, filters=None):
    filters = filters or parser.parse_filters(text, list(Category.objects.values_list("slug", flat=True)))
    products = _keyword_search(filters)
    widened = ""
    if not products.exists() and filters["q"] and filters["category"]:
        # No exact match for the words: say so honestly, then show the category instead.
        widened = f"I couldn't find “{filters['q']}” exactly, so here are popular picks from the same category. "
        filters = {**filters, "q": ""}
        products = _keyword_search(filters)
    count = products.count()
    if not count:
        return reply("I couldn't find anything matching that. Try a wider price range or a different word.",
                     chips=["Show me deals", "Recommend something for me"],
                     link=_link("Browse all products", reverse("store:product_list")))
    # The assistant keeps no memory between messages, so follow-up chips carry the whole question:
    # the button says "Cheapest first" but sends "phones under 20k cheapest first".
    base = parser.SORT_PATTERN.sub("", text).strip(" ,.")
    chips = [_chip("Cheapest first", f"{base} cheapest"), _chip("Best rated", f"{base} best rated")] if count > 1 else []
    return reply(widened + _describe(filters, count), products[:MAX_CARDS], chips=chips,
                 link=_link(f"See all {count} results", _filters_url(filters)))


def _chip(label, message):
    return {"label": label, "message": message}


# --------------------------------------------------------------------- similar items
def _find_product(name):
    """The catalog product whose name best matches what the shopper typed (character TF-IDF)."""
    products = list(Product.objects.filter(is_active=True).only("id", "name"))
    if not products or not name:
        return None
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
    matrix = vectorizer.fit_transform([p.name.lower() for p in products])
    scores = cosine_similarity(vectorizer.transform([name.lower()]), matrix)[0]
    best = int(scores.argmax())
    return products[best] if scores[best] >= PRODUCT_MATCH_THRESHOLD else None


def similar(text, request, current_product=None):
    target = parser.similar_target(text) or ""
    product = current_product if target in {"", "this", "this one", "it"} else _find_product(target)
    if product is None:
        return reply("Which product do you mean? Try “something like” followed by its name.",
                     chips=["Something like Atomic Habits", "Something like iPhone 13 Pro"])
    product = Product.objects.select_related("category").get(pk=product.pk)
    suggestions = rec_services.similar_products(product, limit=MAX_CARDS)
    return reply(f"Here are products similar to {product.name}.", [s.product for s in suggestions],
                 link=_link(f"Open {product.name}", product.get_absolute_url()))


def for_you(text, request):
    mode, suggestions = rec_services.recommended_for(request.user, limit=MAX_CARDS)
    if mode == "personal":
        intro = "Picked for you, based on what you've viewed and bought recently."
    else:
        intro = "These are popular right now. Log in and browse a little, and I'll personalise this."
    return reply(intro, [s.product for s in suggestions])


def deals(text, request):
    return reply("Today's biggest discounts on products in stock:", store_services.deal_products(limit=MAX_CARDS),
                 link=_link("See all deals", f"{reverse('store:product_list')}?sort=discount"))


# --------------------------------------------------------------------- your account (private data)
def order_status(text, request):
    if not request.user.is_authenticated:
        login = f"{reverse('accounts:login')}?{urlencode({'next': reverse('store:order_list')})}"
        return reply("Please log in to check your orders. I can only show orders to the person who placed them.",
                     link=_link("Log in", login))
    # Only ever look inside the logged-in user's own orders.
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    number = parser.order_number(text)
    order = orders.filter(pk=number).first() if number else orders.first()
    if order is None:
        if number:
            return reply(f"I couldn't find order RM-{number:06d} in your account. Check the number on your order page.",
                         link=_link("Your orders", reverse("store:order_list")))
        return reply("You haven't placed any orders yet.", chips=["Show me deals"])
    items = sum(item.quantity for item in order.items.all())
    progress = {Order.Status.PLACED: "has been placed and is being packed",
                Order.Status.SHIPPED: "has shipped and is on its way",
                Order.Status.DELIVERED: "was delivered"}[order.status]
    text = (f"Order {order.order_number} ({items} item{'s' if items != 1 else ''}, {inr(order.total)}) "
            f"{progress}. You ordered it on {order.created_at:%d %b %Y}.")
    return reply(text, link=_link("Track this order", order.get_absolute_url()))


def cart(text, request):
    totals = cart_service.summary(cart_service.get_cart(request))
    if not totals["count"]:
        return reply("Your cart is empty.", chips=["Show me deals", "Recommend something for me"])
    text = f"You have {totals['count']} items in your cart, {inr(totals['total'])} in total."
    if totals["free_shipping_remaining"]:
        text += f" Add {inr(totals['free_shipping_remaining'])} more for free delivery."
    return reply(text, [item.product for item in totals["items"]][:MAX_CARDS],
                 link=_link("Go to cart", reverse("store:cart")))


# --------------------------------------------------------------------- FAQs and small talk
def faq_delivery(text, request):
    free, fee = inr(store_services.FREE_SHIPPING_THRESHOLD), inr(store_services.SHIPPING_FEE)
    return reply(f"Delivery is free on orders of {free} or more. Smaller orders pay a flat {fee}. "
                 "You can follow every order from Placed to Shipped to Delivered on your orders page.")


def faq_payment(text, request):
    return reply("You can pay by UPI, card or cash on delivery. This is a demo store, so payments are simulated "
                 "and no real money is charged. Never enter real card details.")


def faq_returns(text, request):
    return reply("This is a demo store, so there are no real returns or refunds. In a live shop this answer would "
                 "explain the return window and how refunds are paid.", link=_link("Your orders", reverse("store:order_list")))


def about(text, request):
    return reply("RecoMart is a B.Tech CSE full stack lab project. Recommendations come from a K-Means and cosine "
                 "similarity model trained on the catalog and on simulated shopper activity. Payments are simulated.")


def greeting(text, request):
    name = request.user.first_name if request.user.is_authenticated else ""
    hello = f"Hi {name}!" if name else "Hi!"
    return reply(f"{hello} I'm the RecoMart assistant. I can find products, suggest similar ones, and check your "
                 "cart and orders. What are you looking for?", chips=START_CHIPS)


def thanks(text, request):
    return reply("Happy to help. Ask me anything else whenever you like.", chips=START_CHIPS[:3])


def help_(text, request):
    return reply("Try asking me things like these:", chips=START_CHIPS)


def fallback(text, request):
    """Not sure what was meant: try it as a plain product search before giving up."""
    filters = parser.parse_filters(text, list(Category.objects.values_list("slug", flat=True)))
    if filters["q"]:
        products = _keyword_search(filters)
        if products.exists():
            return search(text, request, filters)
        return reply(f"I couldn't find “{filters['q']}” in the store. Try another word, or browse a category.",
                     chips=["Show me deals", "Recommend something for me", "Help"],
                     link=_link("Browse all products", reverse("store:product_list")))
    return reply("Sorry, I didn't understand that. I can search products, suggest similar ones, and check your "
                 "cart, orders, delivery and payment options.", chips=START_CHIPS)


HANDLERS = {
    "search": search, "similar": similar, "for_you": for_you, "deals": deals,
    "order_status": order_status, "cart": cart,
    "faq_delivery": faq_delivery, "faq_payment": faq_payment, "faq_returns": faq_returns, "about": about,
    "greeting": greeting, "thanks": thanks, "help": help_, "fallback": fallback,
}
