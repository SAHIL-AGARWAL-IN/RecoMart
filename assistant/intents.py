"""Work out what a chat message is asking for (its "intent").

Two layers, both easy to explain:
  1. Rules first: an order number means order_status; "like X" means similar items;
     a price, rating or product word means a product search.
  2. Otherwise compare the message with example phrases for every intent using TF-IDF on
     character n-grams and cosine similarity (the same idea as the recommender, but for text).
     Character n-grams ("ord", "rde", "der") make small typos like "ordr" still match.
     If the best match is too weak, the answer is "fallback".
"""
from dataclasses import dataclass
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import parser

CONFIDENCE_THRESHOLD = 0.35

EXAMPLES = {
    "search": [
        "show me shoes", "show me running shoes", "find a phone", "i want a cheap lipstick", "looking for a laptop",
        "do you have headphones", "search for perfume", "buy a watch", "i need a new dress", "show me books",
        "toys for kids", "kitchen items",
    ],
    "similar": [
        "something like this", "similar products", "show me similar items", "alternatives to this",
        "more like this one", "anything similar",
    ],
    "for_you": [
        "recommend something for me", "what should i buy", "suggest products i might like", "recommendations for me",
        "pick something for me", "what would i like", "surprise me", "personal recommendations",
    ],
    "order_status": [
        "where is my order", "track my order", "has my order shipped", "has my parcel shipped", "order status",
        "when will my order arrive", "my order", "delivery status of my order", "is my package delivered",
        "check my order",
    ],
    "cart": [
        "what's in my cart", "show my cart", "show my bag", "cart total", "how many items in my cart",
        "my basket", "view cart", "what did i add",
    ],
    "deals": [
        "any offers today", "show me deals", "what's on sale", "discounts", "best offers", "todays deals",
        "any discount", "sale items",
    ],
    "faq_delivery": [
        "how much is delivery", "is shipping free", "free shipping", "delivery charges", "shipping cost",
        "how long does delivery take", "delivery time", "do you deliver to my city", "shipping fee",
    ],
    "faq_payment": [
        "can i pay with upi", "payment options", "do you accept cash on delivery", "cod available",
        "can i pay by card", "how can i pay", "is payment safe", "payment methods", "pay with credit card",
    ],
    "faq_returns": [
        "can i return a product", "refund policy", "how do returns work", "return policy", "i want a refund",
        "exchange a product", "how to return", "cancel my order",
    ],
    "about": [
        "what is recomart", "who made this", "is this a real shop", "about this store", "are payments real",
        "is this a demo", "how do recommendations work",
    ],
    "greeting": ["hi", "hello", "hello there", "hey", "good morning", "good evening", "namaste", "hii"],
    "thanks": ["thanks", "thank you", "thank you so much", "great thanks", "ok thanks", "bye", "goodbye"],
    "help": ["what can you do", "help", "how does this work", "help me", "what can i ask", "how to use this chat"],
}


@dataclass
class Intent:
    name: str
    confidence: float


@lru_cache(maxsize=1)
def _model():
    """Fit TF-IDF on all example phrases once, the first time it's needed."""
    labels, phrases = [], []
    for name, examples in EXAMPLES.items():
        labels += [name] * len(examples)
        phrases += examples
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
    return vectorizer, vectorizer.fit_transform(phrases), labels


def _nearest_example(text):
    vectorizer, matrix, labels = _model()
    scores = cosine_similarity(vectorizer.transform([text.lower()]), matrix)[0]
    best = int(scores.argmax())
    return labels[best], float(scores[best])


def classify(text, category_slugs=()):
    """The intent of a message, with a confidence between 0 and 1."""
    if parser.order_number(text):
        return Intent("order_status", 1.0)
    if parser.similar_target(text):
        return Intent("similar", 1.0)

    name, confidence = _nearest_example(text)
    filters = parser.parse_filters(text, category_slugs or parser.GENERAL_WORDS.values())
    asks_for_products = parser.has_filters(filters)
    if asks_for_products and (confidence < 0.6 or name in {"search", "deals", "help", "greeting", "fallback"}):
        return Intent("search", max(confidence, 0.6))
    if confidence < CONFIDENCE_THRESHOLD:
        return Intent("fallback", confidence)
    return Intent(name, confidence)
