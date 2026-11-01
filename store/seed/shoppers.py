"""Simulated shoppers: browsing sessions, carts, wishlists, orders and reviews.

Everything here is SIMULATED demo data, labelled as such in the README and on the ML Insights
page. It is given structure on purpose so the recommender has real patterns to find:
  * every shopper prefers two categories and browses them most of the time;
  * well-rated products are more popular ("appeal");
  * a few product pairs per category are often bought together (for "Frequently bought together").
"""
import string
from datetime import timedelta

from django.utils import timezone

from recommender.models import RecommendationEvent
from store.models import Interaction, Order, OrderItem, Review, WishlistItem
from store.services import shipping_fee_for

DAYS_OF_HISTORY = 90
REC_EVENT_DAYS = 30
# Real shops show mostly 3-5 star reviews, with product averages in this range.
RATING_AVG_RANGE = (3.8, 4.7)
MIN_REVIEWS_PER_PRODUCT = 5
# The same base click rate is used for both A/B variants, so the seed does not decide the test.
SIMULATED_CTR = {"similar": 0.05, "for_you": 0.07, "trending": 0.04, "fbt": 0.06}

COMMENTS = {
    5: ["Excellent quality, totally worth the price.", "Loved it! Exactly as described.",
        "Superb product, fast delivery too.", "Best purchase this month. Highly recommend."],
    4: ["Very good, minor issues but happy overall.", "Good value for money.",
        "Nice product, packaging could be better.", "Works well, would buy again."],
    3: ["It's okay. Does the job.", "Average quality for the price.", "Decent, but expected a bit more."],
    2: ["Not great, quality feels cheap.", "Below expectations, delivery was slow."],
    1: ["Disappointed. Would not recommend.", "Stopped working after a week."],
}
TYPE = Interaction.Type


class ShopperSimulator:
    def __init__(self, rng, fake, products, base_ratings, now=None):
        self.rng = rng
        self.fake = fake
        self.now = now or timezone.now()
        self.products = products
        self.base_ratings = base_ratings  # product id -> rating from the source catalog
        self.by_category = {}
        for product in products:
            self.by_category.setdefault(product.category.slug, []).append(product)
        self.category_slugs = sorted(self.by_category)
        # Popular products get viewed more: weight grows with the source rating.
        self.appeal = {p.id: (base_ratings[p.id] ** 3) * rng.uniform(0.5, 1.5) for p in products}
        self.partner = self._make_bundles()

        self.interactions, self.wishlist, self.reviews = [], [], []
        self._wishlist_keys, self._review_keys = set(), set()
        self.order_count = 0

    # ----------------------------------------------------------------- helpers
    def _make_bundles(self, pairs_per_category=4):
        partner = {}
        for items in self.by_category.values():
            pool = list(items)
            self.rng.shuffle(pool)
            for a, b in zip(pool[0:pairs_per_category * 2:2], pool[1:pairs_per_category * 2:2]):
                partner[a.id], partner[b.id] = b, a
        return partner

    def _pick_products(self, category, k):
        """Weighted sample without replacement: appealing products are picked more often."""
        pool = list(self.by_category[category])
        chosen = []
        for _ in range(min(k, len(pool))):
            weights = [self.appeal[p.id] for p in pool]
            product = self.rng.choices(pool, weights=weights)[0]
            pool.remove(product)
            chosen.append(product)
        return chosen

    def _log(self, product, kind, when, user=None, session_key="", quantity=1):
        self.interactions.append(Interaction(user=user, session_key=session_key, product=product,
                                             interaction_type=kind, quantity=quantity, timestamp=when))

    def _rating_for(self, product):
        """Mostly 3-5 stars; better products (higher source rating) get more 5s."""
        quality = min(1.0, max(0.0, (self.base_ratings[product.id] - 2.5) / 2.5))  # 0..1
        weights = {1: 0.02, 2: 0.04, 3: 0.20 - 0.08 * quality, 4: 0.42, 5: 0.22 + 0.22 * quality}
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def _add_review(self, user, product, when):
        key = (user.id, product.id)
        if key in self._review_keys:
            return
        self._review_keys.add(key)
        rating = self._rating_for(product)
        self.reviews.append(Review(user=user, product=product, rating=rating,
                                   comment=self.rng.choice(COMMENTS[rating]), created_at=when))
        self._log(product, TYPE.REVIEW, when, user=user)

    # ----------------------------------------------------------------- shoppers
    def simulate_customer(self, user, preferred, sessions):
        for _ in range(sessions):
            when = self.now - timedelta(days=self.rng.uniform(0, DAYS_OF_HISTORY))
            category = self.rng.choice(preferred) if self.rng.random() < 0.8 else self.rng.choice(self.category_slugs)
            viewed = self._pick_products(category, self.rng.randint(2, 6))
            for product in viewed:
                when += timedelta(minutes=self.rng.uniform(0.5, 4))
                self._log(product, TYPE.VIEW, when, user=user)

            carted = [p for p in viewed if self.rng.random() < 0.3]
            for product in carted:
                self._log(product, TYPE.CART, when, user=user)

            for product in viewed:
                if self.rng.random() < 0.12 and (user.id, product.id) not in self._wishlist_keys:
                    self._wishlist_keys.add((user.id, product.id))
                    self.wishlist.append(WishlistItem(user=user, product=product, added_at=when))
                    self._log(product, TYPE.WISHLIST, when, user=user)

            if carted and self.rng.random() < 0.55:
                self._place_order(user, carted, when + timedelta(minutes=self.rng.uniform(2, 15)))

    def simulate_guest(self, sessions=1):
        session_key = "".join(self.rng.choices(string.ascii_lowercase + string.digits, k=32))
        for _ in range(sessions):
            when = self.now - timedelta(days=self.rng.uniform(0, DAYS_OF_HISTORY))
            for product in self._pick_products(self.rng.choice(self.category_slugs), self.rng.randint(1, 5)):
                when += timedelta(minutes=self.rng.uniform(0.5, 3))
                self._log(product, TYPE.VIEW, when, session_key=session_key)
                if self.rng.random() < 0.15:
                    self._log(product, TYPE.CART, when, session_key=session_key)

    def _place_order(self, user, products, when):
        items = list(products)
        for product in products:  # bundle partners are often bought together
            partner = self.partner.get(product.id)
            if partner and partner not in items and self.rng.random() < 0.6:
                items.append(partner)

        lines = [(p, 2 if self.rng.random() < 0.15 else 1) for p in items]
        subtotal = sum(p.effective_price * qty for p, qty in lines)
        fee = shipping_fee_for(subtotal)
        age_days = (self.now - when).days
        status = Order.Status.DELIVERED if age_days >= 7 else Order.Status.SHIPPED if age_days >= 2 else Order.Status.PLACED
        method = self.rng.choices(list(Order.PaymentMethod), weights=[5, 3, 2])[0]
        payment_ref = "" if method == Order.PaymentMethod.COD else "SIM-" + "".join(
            self.rng.choices(string.ascii_uppercase + string.digits, k=6))

        order = Order.objects.create(
            user=user, status=status, full_name=user.get_full_name(), phone=self._phone(),
            address_line=self.fake.street_address(), city=self.fake.city(), state=self.fake.state(),
            pincode=f"{self.rng.randint(110001, 855999)}", payment_method=method, payment_ref=payment_ref,
            subtotal=subtotal, shipping_fee=fee, total=subtotal + fee, created_at=when,
        )
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=p, product_name=p.name, unit_price=p.effective_price, quantity=qty)
            for p, qty in lines
        ])
        self.order_count += 1
        for product, qty in lines:
            self._log(product, TYPE.PURCHASE, when, user=user, quantity=qty)
            if status == Order.Status.DELIVERED and self.rng.random() < 0.45:
                review_time = min(self.now, when + timedelta(days=self.rng.uniform(3, 10)))
                self._add_review(user, product, review_time)

    def _phone(self):
        return f"{self.rng.choice('6789')}{self.rng.randint(0, 999_999_999):09d}"

    def top_up_reviews(self, customers, minimum=MIN_REVIEWS_PER_PRODUCT):
        """Make sure every product has a few ratings, so no card says '0 reviews'."""
        counts = {}
        for review in self.reviews:
            counts[review.product.id] = counts.get(review.product.id, 0) + 1
        for product in self.products:
            missing = minimum - counts.get(product.id, 0)
            if missing > 0:
                reviewers = self.rng.sample(customers, k=min(len(customers), missing + self.rng.randint(0, 3)))
                for user in reviewers:
                    when = self.now - timedelta(days=self.rng.uniform(1, DAYS_OF_HISTORY))
                    self._add_review(user, product, when)

    def calibrate_ratings(self, low=RATING_AVG_RANGE[0], high=RATING_AVG_RANGE[1]):
        """Nudge single reviews up or down a star until each product's average is in [low, high]."""
        by_product = {}
        for review in self.reviews:
            by_product.setdefault(review.product.id, []).append(review)
        for reviews in by_product.values():
            average = lambda: sum(r.rating for r in reviews) / len(reviews)
            while average() > high:
                review = max(reviews, key=lambda r: (r.rating, self.rng.random()))
                review.rating -= 1
            while average() < low:
                review = min(reviews, key=lambda r: (r.rating, self.rng.random()))
                review.rating += 1
            for review in reviews:  # keep the comment consistent with the final rating
                if review.comment not in COMMENTS[review.rating]:
                    review.comment = self.rng.choice(COMMENTS[review.rating])

    # ------------------------------------------------- recommendation events
    def simulate_rec_events(self, customers, count=2500):
        """Impressions and clicks on recommendation widgets, for the CTR and A/B charts."""
        events = []
        widgets = list(SIMULATED_CTR)
        for _ in range(count):
            widget = self.rng.choices(widgets, weights=[5, 2, 2, 1])[0]
            variant = self.rng.choice("AB") if widget == "similar" else "-"
            product = self.rng.choices(self.products, weights=[self.appeal[p.id] for p in self.products])[0]
            source = None
            if widget in ("similar", "fbt"):
                source = self.rng.choice(self.by_category[product.category.slug])
            user = self.rng.choice(customers) if self.rng.random() < 0.7 else None
            when = self.now - timedelta(days=self.rng.uniform(0, REC_EVENT_DAYS))
            common = dict(user=user, widget=widget, variant=variant, product=product, source_product=source)
            events.append(RecommendationEvent(event_type="impression", created_at=when, **common))
            if self.rng.random() < SIMULATED_CTR[widget]:
                events.append(RecommendationEvent(event_type="click", created_at=when + timedelta(seconds=20),
                                                  **common))
        return events
