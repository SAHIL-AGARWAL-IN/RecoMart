"""How the assistant reads a message: filters from text, and which intent it is (no database needed)."""
from decimal import Decimal

from django.test import SimpleTestCase

from assistant import intents, parser

CATEGORIES = ["electronics", "fashion", "books", "home", "sports", "beauty", "toys", "grocery"]


class FilterParserTests(SimpleTestCase):
    def parse(self, text):
        return parser.parse_filters(text, CATEGORIES)

    def test_price_ceiling_with_k_and_rupee_sign(self):
        self.assertEqual(self.parse("phones under 20k")["max_price"], Decimal("20000"))
        self.assertEqual(self.parse("shoes below ₹2,500")["max_price"], Decimal("2500"))

    def test_price_floor_and_range(self):
        self.assertEqual(self.parse("watches above 5000")["min_price"], Decimal("5000"))
        between = self.parse("laptops between 40000 and 60000")
        self.assertEqual((between["min_price"], between["max_price"]), (Decimal("40000"), Decimal("60000")))

    def test_rating(self):
        self.assertEqual(self.parse("4 star books")["rating"], 4)
        self.assertEqual(self.parse("toys rated 3+")["rating"], 3)

    def test_category_from_everyday_words(self):
        self.assertEqual(self.parse("phones under 20000")["category"], "electronics")
        self.assertEqual(self.parse("a good novel")["category"], "books")
        self.assertEqual(self.parse("lipstick")["category"], "beauty")

    def test_sort_words(self):
        self.assertEqual(self.parse("cheapest headphones")["sort"], "price_asc")
        self.assertEqual(self.parse("best rated perfume")["sort"], "rating")
        self.assertEqual(self.parse("biggest discounts on shoes")["sort"], "discount")

    def test_keywords_drop_filler_words(self):
        self.assertEqual(self.parse("show me some wireless earbuds under 3000")["q"], "wireless earbuds")

    def test_order_number(self):
        self.assertEqual(parser.order_number("where is RM-000123?"), 123)
        self.assertEqual(parser.order_number("status of order rm123"), 123)
        self.assertIsNone(parser.order_number("where is my order"))

    def test_similar_target(self):
        self.assertEqual(parser.similar_target("something like Atomic Habits"), "atomic habits")
        self.assertEqual(parser.similar_target("show me products similar to the iphone 13 pro"), "iphone 13 pro")


class IntentTests(SimpleTestCase):
    EXAMPLES = {
        "search": ["phones under 20000", "show me running shoes", "I want a cheap lipstick", "4 star books"],
        "similar": ["something like atomic habits", "similar to iphone 13", "alternatives to the oppo k1"],
        "for_you": ["recommend something for me", "what should I buy", "suggest products I might like"],
        "order_status": ["where is my order", "track my order", "has my parcel shipped", "status of RM-000123"],
        "cart": ["what's in my cart", "show my bag", "cart total"],
        "deals": ["any offers today", "show me deals", "what's on sale"],
        "faq_delivery": ["how much is delivery", "is shipping free", "delivery charges"],
        "faq_payment": ["can I pay with upi", "do you accept cash on delivery", "payment options"],
        "faq_returns": ["can I return a product", "refund policy", "how do returns work"],
        "greeting": ["hi", "hello there", "good morning"],
        "help": ["what can you do", "help", "how does this work"],
    }

    def test_everyday_phrases_reach_the_right_intent(self):
        wrong = []
        for expected, phrases in self.EXAMPLES.items():
            for phrase in phrases:
                got = intents.classify(phrase).name
                if got != expected:
                    wrong.append(f"{phrase!r}: expected {expected}, got {got}")
        self.assertEqual(wrong, [])

    def test_small_typos_still_work(self):
        self.assertEqual(intents.classify("wher is my ordr").name, "order_status")
        self.assertEqual(intents.classify("delivary charges").name, "faq_delivery")

    def test_nonsense_falls_back(self):
        result = intents.classify("qwzx plmok vbnr")
        self.assertEqual(result.name, "fallback")
        self.assertLess(result.confidence, intents.CONFIDENCE_THRESHOLD)
