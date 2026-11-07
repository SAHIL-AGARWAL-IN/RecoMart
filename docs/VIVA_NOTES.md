# RecoMart: viva notes

This file gets one section per build phase. Each section covers what we built, why we built it that way, and questions an examiner is likely to ask, with short answers you can say in your own words.

---

## Phase 1: Foundation (project setup, models, admin, seed data)

### What we built
- **A Django project with 4 apps.** Each app has one job, which keeps the code easy to find.
  - `config/`: settings and the root URLs
  - `accounts/`: users and roles
  - `store/`: products, cart, orders, reviews and wishlist
  - `recommender/`: the ML engine
  - `dashboard/`: admin analytics
- **Settings read secrets from `.env`** using python-dotenv. The secret key and DEBUG never go into git. Changing `DB_ENGINE=postgres` switches from SQLite to PostgreSQL with no code changes.
- **A custom `User` model** extends Django's `AbstractUser` and adds a `role` field (Customer / Admin). Passwords are hashed automatically with PBKDF2, so we never store plain text.
- **All data models:** Category, Product, ProductImage, Interaction, Cart, CartItem, Order, OrderItem, Review and WishlistItem. On the ML side: RecommendationData, TrainingRun and RecommendationEvent.
- **The Django admin** at `/admin/` has search, filters, thumbnails and inline order items.
- **`python manage.py seed_data`** builds a realistic demo store:
  - About 150 products in 8 categories. Real names, brands, descriptions and photos come from the free DummyJSON test API, using a committed snapshot.
  - Books and toys, which DummyJSON lacks, are written by us and their cover images are drawn with Pillow.
  - Prices are converted from USD to INR and rounded to shop-style prices like ₹849.
  - 40 **simulated** customers plus guests. They browse, add to cart, wishlist, place orders and write reviews over the last 90 days.

### Key design decisions
| Decision | Why |
|---|---|
| Custom User model from the very first migration | Django can't easily switch the user model later. A `role` field is simpler than a separate Profile table. |
| `Interaction` table (view / cart / wishlist / purchase / review) | This behaviour data is what the ML model learns popularity and personal taste from. |
| `RecommendationEvent` kept separate from `Interaction` | Interactions describe *shoppers*. Events measure *the recommender* (impressions and clicks), so we can compute click-through rate (CTR) and compare the A/B variants. |
| `OrderItem` copies the product name and price | If a price changes later, old orders must still show what the customer actually paid. |
| `Review.save()` recalculates `Product.rating_avg` | Ratings stay correct automatically, and ratings are one of the ML features. |
| Simulated shoppers prefer two categories, and some products are "bundles" | Random data has no patterns, so the ML would have nothing to learn. Built-in structure gives realistic clusters and "frequently bought together" pairs. Both A/B variants use the *same* simulated click rate, so the seed doesn't rig the test. |
| DummyJSON snapshot committed, images downloaded once into `media/` | Every teammate gets the same catalog. Only the first seed needs internet. |
| Shared demo password hashed once | Password hashing is deliberately slow, and hashing once makes seeding 40 users fast. |

### Likely viva questions
**Q: Why Django?**
A: It is "batteries included". It comes with an ORM, authentication, an admin panel, forms, CSRF protection and templates. Building those ourselves would take weeks.

**Q: What is an ORM?**
A: An Object-Relational Mapper. We write Python classes (models) and Django turns them into SQL tables and queries. For example, `Product.objects.filter(price__lt=500)` becomes a `SELECT ... WHERE price < 500`.

**Q: What are migrations?**
A: Version-controlled files describing changes to the database schema. `makemigrations` creates them from our models, and `migrate` applies them to the database.

**Q: How are passwords stored?**
A: As a salted PBKDF2-SHA256 hash, never as plain text. `check_password()` hashes the typed password the same way and compares the two hashes.

**Q: Why `DecimalField` for money instead of float?**
A: Floats have rounding errors (0.1 + 0.2 ≠ 0.3). Decimal is exact, which money needs.

**Q: What is the difference between `ForeignKey`, `OneToOneField` and `on_delete`?**
A:
- A `ForeignKey` is many-to-one: many products belong to one category.
- A `OneToOneField` means exactly one: each user has one cart.
- `on_delete` decides what happens when the parent row is deleted:
  - `CASCADE` deletes the children too
  - `PROTECT` blocks the delete; we use it so a product that is in old orders can't be deleted
  - `SET_NULL` keeps the child and clears the link

**Q: Is the data real?**
A: The product catalog is real test data from DummyJSON. Users, orders, reviews and interactions are **simulated** by `seed_data`, and the app says so wherever they are shown.

**Q: Why store `session_key` on Interaction and Cart?**
A: Guests have no user account. Django gives every visitor a session cookie, so we use its key to remember a guest's cart and the products they viewed.

---

## Phase 2: Storefront UI (theme, auth, home, product list, product detail)

### What we built
- **Theme and layout.**
  - `templates/base.html` is the master layout. Every page `{% extends %}` it and fills in blocks like `title` and `content`. The navbar, footer and toasts are `{% include %}`-d partials.
  - `static/css/theme.css` defines all colours, radii and shadows as CSS custom properties, then points Bootstrap's own variables at them. That's why it doesn't look like default Bootstrap.
  - Bootstrap, the icons and the fonts are in `static/vendor/`, so the site works with no internet.
- **Home page.**
  - **Hero:** real product photos drawn as three "clusters" joined by lines, a picture of what K-Means will do in Phase 4.
  - **Category tiles.**
  - **Trending now:** products with the most weighted activity in the last 30 days.
  - **Today's deals:** in-stock products with the biggest discount.
- **Product list and category pages.**
  - Filters for search, price range, minimum rating and sort, all built from Django ORM QuerySets.
  - Pagination of 12 per page.
  - On phones, the filter panel slides in from the side (Bootstrap's responsive offcanvas).
- **Product detail page.**
  - Image gallery and a sticky buy box with price, savings and stock.
  - Description and Reviews tabs, with a star-rating breakdown.
  - Opening a product **logs a "view" Interaction** (training data for the ML) and adds it to the **recently viewed** list in the session.
- **Accounts.** Register (logs you straight in), log in, log out (POST only) and an editable profile.
- **Template tags.**
  - `inr` formats money the Indian way: ₹13,59,999.
  - `stars` draws full, half and empty stars.
  - `query_with` keeps filters in pagination links.

### Key design decisions
| Decision | Why |
|---|---|
| Template inheritance (`base.html` plus partials) | Write the header and footer once. Every page stays consistent, and a change in one place updates every page. |
| Design tokens in CSS custom properties | Brand colours live in one place, and dark mode only has to swap the token values. |
| Product price filters use `Coalesce(discount_price, price)` | Shoppers filter by what they actually pay, not by the crossed-out MRP. |
| Trending = weighted interaction count over 30 days | A purchase (weight 3) says more than a view (weight 1), and only recent activity counts. |
| `filter_products()` lives in `services.py`, not in the view | The same function will power the AJAX filter API in Phase 3. Views stay thin and easy to test. |
| Logout is a POST form | A logout link (GET) could be triggered by another website. POST with a CSRF token can't. |
| Explicit `order_by` after `annotate(Count(...))` | Django ignores a model's default ordering in GROUP BY queries. We found this bug through a screenshot. |
| Accessibility built in | Skip link, labels on every input, visible focus rings, alt text, `aria-live` toasts and a correct heading order. We checked the UI against the Web Interface Guidelines and fixed what it flagged. |

### Likely viva questions
**Q: What is template inheritance?**
A: `base.html` defines the page skeleton with named `{% block %}`s. A child template says `{% extends "base.html" %}` and only overrides the blocks it needs, such as `content`. Shared pieces like the navbar are separate files pulled in with `{% include %}`.

**Q: How does the search work?**
A: The search box sends `?q=...` to `/products/`. The view filters with `Q(name__icontains=q) | Q(brand__icontains=q) | ...`. `icontains` is a case-insensitive "contains", which becomes SQL `LIKE '%q%'`. The `Q` objects let us OR conditions together.

**Q: How does pagination work?**
A: Django's `Paginator` splits the QuerySet into pages of 12. `page.start_index` and `end_index` give "Showing 1–12 of 22". The queryset is lazy, so only the 12 rows for the current page are fetched with `LIMIT/OFFSET`.

**Q: What is a context processor?**
A: A function that adds variables to *every* template. Ours (`store_nav`) adds the category list, because the navbar on every page needs it.

**Q: How do you track what a guest viewed without an account?**
A: Django sessions. Every visitor gets a session cookie. We store the viewed product ids in `request.session["recently_viewed"]` and save each view as an `Interaction` row with the `session_key`.

**Q: What is CSRF and how is it handled?**
A: Cross-Site Request Forgery is when another site tricks your browser into submitting a form to ours. Every POST form includes `{% csrf_token %}`, and Django rejects POSTs without a matching token. Our JavaScript sends it in the `X-CSRFToken` header.

**Q: How do you format ₹13,59,999?**
A: With our own `inr` template filter. The Indian system groups the last 3 digits, then pairs of 2. It is unit-tested in `store/tests/test_tags.py`.

**Q: How is the site responsive?**
A:
- The Bootstrap grid (`row-cols-2 row-cols-md-3`) changes columns per screen width.
- Media queries in `theme.css` handle the header and the category tiles.
- The filter panel becomes a slide-in drawer on phones.
- We tested at 375 px (phone), 768 px (tablet) and 1280 px (laptop) with Playwright screenshots.

### Phase 2 revisions (after review)
- **Navbar:** a wishlist heart and a cart icon with count badges, and an account dropdown (Profile, Orders, Dashboard for admins, Log out). Guests get Log in / Register. The counts come from the `store_nav` context processor, so every page has them. The header search is hidden on the home page, because the hero already has one.
- **Compact cards:** 4 per row on laptops and 5 on wide screens (Bootstrap `row-cols-xl-4 row-cols-xxl-5`). There are 20 products per page, because 20 divides by both 4 and 5, so rows are always full.
- **Realistic seed data:** review stars are mostly 3–5. Each product's average is calibrated into 3.8–4.7, and about 15% of products are on a 25–50% sale.
- **Bug found by looking at the page:** "Today's deals" wasn't sorted by discount. SQLite stores these prices as whole numbers and did *integer* division, so 6299 / 10999 gave 0 for every product. The fix is to `Cast(..., FloatField())` before dividing. A regression test now guards it.

**Q: Why not compute the discount percentage in Python instead?**
A: Sorting must happen in the database, so `ORDER BY` and `LIMIT` return only the top deals. Loading all products into Python just to sort them would be slow on a big catalog. That's why we annotate the ratio in the query.

**Q: How do the badge counts appear on every page?**
A: Through a context processor, `store/context_processors.py`. Django runs it on every request and adds `cart_count` and `wishlist_count` to every template's context.

---

## Phase 3: Shopping (cart, checkout, orders, wishlist, reviews, live search, AJAX filters)

### What we built
- **Cart** (`store/cart.py`).
  - Guests and logged-in users can add, change and remove items. Quantities are capped at stock.
  - The summary shows subtotal, delivery and total, and a "₹X more for free delivery" bar.
  - When a guest logs in, their cart is merged into their account.
- **AJAX everywhere.** The "Add to cart" button, the cart page, the wishlist heart and the filters all use `fetch()` with JSON, so the page never reloads. A toast confirms each action, and the navbar badges update live.
- **Checkout** (`services.place_order`).
  - Delivery address plus a simulated payment by UPI, card or cash on delivery.
  - The UPI ID, card number (Luhn check), expiry, CVV, PIN code and phone are all validated.
  - The order, its items and the "purchase" interactions are created, stock goes down and the cart is cleared, all in one database transaction.
- **Orders.** A thank-you page, an order history, and an order detail page with a Placed → Shipped → Delivered timeline.
- **Wishlist.** A heart on every product toggles it over AJAX. Guests are sent to the login page.
- **Reviews.** One review per user per product, which you can edit later. A "Verified purchase" badge shows if you bought it, and the product's average rating updates automatically.
- **Live search.**
  - Results with thumbnails appear under the search box as you type.
  - Matching text is highlighted, and arrow keys, Enter and Escape work.
- **AJAX filters.** Category, price, rating, sort and page change without a reload. Skeleton cards show while loading, and the browser URL updates so the result can be bookmarked.

### Key design decisions
| Decision | Why |
|---|---|
| Guest cart id is stored **inside** the session, not found by session key | Django gives you a new session key when you log in (this prevents "session fixation" attacks). The session data is kept, though, so the cart id survives and we can merge the guest cart into the user's cart. |
| `@transaction.atomic` around `place_order` | All-or-nothing. If any item is out of stock, every change (stock, order, items) is rolled back, so the database never ends up with half an order. |
| Conditional stock update: `filter(stock__gte=qty).update(stock=F("stock") - qty)` | The check and the decrement happen in one SQL statement inside the database. Two shoppers can't both buy the last item, because the second update matches 0 rows. |
| `OrderItem.unit_price` is copied from the product | The order keeps the price paid, even if the product's price changes later. |
| Only the card's last 4 digits are kept, and the CVV is never stored | Real shops must never store full card numbers (PCI rules). We copy the habit even though payment is fake. |
| Order pages use `get_object_or_404(Order, pk=pk, user=request.user)` | Someone else's order id gives "not found", so another person's address can't leak by guessing ids. |
| The filter form works without JavaScript; `filters.js` only upgrades it | Progressive enhancement. The site still works if JS fails, and the server stays the single source of truth for the grid HTML. |
| Live search waits 300 ms and cancels older requests (AbortController) | Typing "phone" doesn't send 5 requests, and a slow old answer can't overwrite a newer one. |
| Event delegation (`document.addEventListener("click", …)`) | One listener handles every "Add to cart" button, including cards loaded later by AJAX. |

### Likely viva questions
**Q: What is AJAX, and where do you use it?**
A: It means JavaScript asks the server for data in the background with `fetch()` and updates part of the page without a full reload. We use it for add-to-cart, the cart page, the wishlist heart, live search and the product filters. The server answers with `JsonResponse`.

**Q: How is the AJAX request protected from CSRF?**
A: Django sets a `csrftoken` cookie. Our `fetchJSON()` helper in `main.js` reads it and sends it in the `X-CSRFToken` header. Django's CSRF middleware rejects any POST without a matching token.

**Q: What happens if two people buy the last item at the same time?**
A: Each checkout runs `UPDATE product SET stock = stock - qty WHERE id = … AND stock >= qty`. The database runs these one after another. The first succeeds; the second matches 0 rows, so we raise `OutOfStockError`, the transaction rolls back, and that shopper sees a friendly message.

**Q: What does `@transaction.atomic` do?**
A: It wraps the function in a database transaction. If any line raises an error, everything done inside it is undone (rolled back). If it finishes, it is all saved (committed) together.

**Q: How does the cart work for someone who isn't logged in?**
A: We create a `Cart` row with no user and keep its id in `request.session["cart_id"]`. The session is tied to the browser by a cookie. When they log in, a `user_logged_in` signal handler (`accounts/signals.py`) moves the items into their own cart.

**Q: What is a Django signal?**
A: A way to run code when something happens elsewhere in Django, without changing that code. We listen for `user_logged_in` to merge carts.

**Q: What is debouncing?**
A: Waiting until the user stops typing for a short time (300 ms) before acting. Without it, live search would call the server on every key press.

**Q: How do you check a card number without a payment gateway?**
A: With the Luhn algorithm, a checksum every real card number satisfies. From the right, double every second digit (subtract 9 if the result is over 9), add everything up, and the total must divide by 10. `4111 1111 1111 1111` passes.

**Q: Why render the product grid HTML on the server for AJAX, instead of building it in JavaScript?**
A: The same Django template (`_product_results.html`) is used for the normal page and the AJAX update. That way the card design lives in one place, and Django's auto-escaping protects against XSS.

**Q: How does the wishlist heart know a product is already saved?**
A: The `store_nav` context processor puts the set of the user's wishlisted product ids into every template. The card checks `product.id in wishlist_ids` and sets `aria-pressed="true"`, which the CSS uses to show a filled heart.

---

## Phase 4: ML engine (features, training, Joblib, recommendation API, "You may also like")

### What we built
- **`recommender/features.py`** turns each product into a **feature vector** (a list of 332 numbers) with a scikit-learn `Pipeline`:
  1. **TF-IDF** of name + brand + category + description: which words describe the product.
  2. **One-hot** category and brand. Brands that appear only once are grouped as "other".
  3. **Numbers:** log(price) and 90-day activity (views, carts, wishlists, purchases), scaled to 0–1, plus the rating.
  4. Each block gets a weight (words and category 1.0, brand 0.4, numbers 0.3, rating 0.2). Then every row is **L2-normalised** to length 1.
- **`recommender/engine.py`:**
  - **K-Means** for K = 3…12. For each K it records **inertia** (for the elbow method) and the **silhouette score**, and K is the best silhouette.
  - **Ranking:** cosine similarity inside the product's cluster, topped up from the nearest clusters.
  - **PCA** reduces the vectors to 2-D, which the scatter chart in Phase 6 will use.
  - **Saving:** Joblib versions (`recommender/artifacts/recomart_v1.joblib`, `v2`, …).
  - **Serving:** a `Recommender` object loaded **once per process** and cached.
- **`python manage.py train_recommender`** prints every check and saves a `TrainingRun`, a `RecommendationData` row per product, and `Product.feature_vector`.
- **`/api/recommendations/<id>/`** returns JSON, and the **"You may also like"** carousel on the product page fetches it. Skeleton cards show while loading, it scrolls sideways, and the hearts and quick-add buttons work.
- **Measuring it:** every card shown is an *impression*. Opening one is a *click*: the link carries `?rec=similar&src=<id>`, the product page logs the click, then redirects to the clean URL.

### Our training run (150 products, simulated shopper data)
- 150 products × 332 features, 0 missing values, 0 NaNs, every row length 1.000.
- Silhouette rose from 0.15 (K=3) to **0.344 at K=8**, then fell. The elbow of the inertia curve is also at K=8, so **K = 8**.
- Each of the 8 clusters is 100% one category (Grocery, Home & Kitchen, Sports, Books, Electronics, Fashion, Beauty, Toys).
- Sample: for **Oppo A57** the top matches are Oppo K1 (0.835), Oppo F19 Pro Plus (0.760), then iPhones. For **Essence Mascara** they're Red Lipstick, Powder Canister and Red Nail Polish.

### Key design decisions
| Decision | Why |
|---|---|
| L2-normalise every vector | Then cosine similarity is just a dot product (`matrix @ matrix.T`), which is fast and simple. K-Means on unit vectors also groups by *direction*, i.e. by what a product is like. |
| `log(price)` before scaling | Prices run from ₹69 to ₹13 lakh. Without the log, one Rolex would squash every other price close to 0. |
| Block weights (words/category heavy, numbers light) | A cheap phone should still match an expensive phone. Price and popularity only break ties. |
| K by silhouette, with the elbow printed too | The silhouette score measures how well-separated the clusters are, which is a clear rule. The elbow method is a visual check, and here both agree on 8. |
| Rank inside the cluster first, then the nearest clusters | Clustering narrows the search to the right "neighbourhood". Topping up from the nearest clusters means we always have enough suggestions. |
| Train offline with a command, not on every request | Training takes about 4 seconds. Serving a cached list takes microseconds. |
| Joblib with version numbers | We can keep old models, roll back, and show "model v3" in the dashboard. Joblib stores NumPy arrays efficiently. |
| Load the model once and cache it | Reading the file on every request would be slow. `reset_cache()` makes the site use the new version right after retraining. |
| Out-of-stock items go last | Don't recommend things the shopper can't buy. |
| Fallback to popular items in the same category | A product added after training isn't in the model yet, but it still gets sensible suggestions. |
| Redirect after logging a click | Refreshing or sharing the page doesn't count the click twice, and the URL stays clean. |

### Likely viva questions
**Q: Explain TF-IDF.**
A: Term Frequency × Inverse Document Frequency. A word scores high if it appears often in *this* product's text but rarely across all products. "android" is important for a phone; "the" is ignored (a stop word); "new" appears everywhere, so it gets a low weight.

**Q: What is one-hot encoding?**
A: Turning a category into columns of 0/1. For example "Electronics" becomes [1, 0, 0, …]. A model can't use text labels directly, and plain numbers like 1, 2, 3 would wrongly suggest an order.

**Q: What is cosine similarity?**
A: The cosine of the angle between two vectors. 1 means pointing the same way (very similar), 0 means unrelated. Because our vectors have length 1, it equals their dot product.

**Q: How does K-Means work?**
A:
1. Pick K starting centres.
2. Assign every product to its nearest centre.
3. Move each centre to the average of its products.
4. Repeat steps 2–3 until nothing changes.

We run it 10 times from different starting points (`n_init=10`) and keep the best, with `random_state=42` so the result is repeatable.

**Q: How did you choose K?**
A: We tried K = 3 to 12.
- **Inertia** (the total squared distance of products to their centre) always goes down as K grows. The "elbow" is where it stops dropping steeply.
- **Silhouette** (from −1 to 1) compares how close each product is to its own cluster versus the next one, so higher is better.

We pick the best silhouette, and the elbow agreed: K = 8.

**Q: Your 8 clusters are exactly the 8 categories. Isn't that just filtering by category?**
A: No:
- The clusters were *learned* from the data, not given. They match the categories because category, words and brand naturally separate the products, which shows the features work.
- Inside a cluster, the *order* comes from words, brand, price and popularity. That's why an Oppo phone shows other Oppos first, and mascara shows lipstick before body lotion.
- A product can also get suggestions from neighbouring clusters.

**Q: What is PCA, and why use it?**
A: Principal Component Analysis squeezes 332 numbers into 2 while keeping as much variation as possible. We only use it to *draw* the clusters on a 2-D chart (Phase 6), not for recommending.

**Q: Why Joblib and not pickle?**
A: Joblib is built on pickle, but it is much faster and smaller for large NumPy arrays and compresses them. We only load files our own command created, because loading a pickle from an untrusted source can run code.

**Q: How do you make sure a product never recommends itself?**
A: `rank_similar` skips index `i` when ranking product `i`'s list, and a unit test checks every list.

**Q: How do you test an ML model?**
A: On a small fixed dataset with three obvious groups (phones, novels, cookware). Each test checks one thing:
- K = 3 is chosen and each group is one cluster
- no product is in its own list
- the top match always shares the category
- vectors have no NaNs and have length 1
- saving and reloading with Joblib gives identical results
- out-of-stock items go last
- new products get the fallback

**Q: What is a click-through rate (CTR)?**
A: Clicks ÷ impressions. If "You may also like" is shown 1,000 times and opened 50 times, the CTR is 5%. We log both, and Phase 6 compares the A/B variants with it.

---

## Phase 5: Enhancements (personal feed, hybrid ranking, "Why this?", frequently bought together, recently viewed)

### What we built
- **Hybrid ranking.** Every recommendation strip is ordered by
  `final = similarity × 0.60 + popularity × 0.25 + recency × 0.15`. The weights are in `settings.RECOMMENDER["HYBRID_WEIGHTS"]`.
  - *similarity*: the cosine similarity from the trained model (0–1)
  - *popularity*: weighted shopper activity in the last 30 days (purchase 3, cart/wishlist/review 2, view 1), log-scaled to 0–1 and cached for 5 minutes
  - *recency*: `exp(−days since the product was added / 90)`, so new products get a small boost
- **"Recommended for you"** on the home page for logged-in shoppers:
  1. Take their last 20 interactions. Each is weighted by type and halves in weight every 30 days.
  2. Average those products' feature vectors into one **taste vector**.
  3. Find the products closest to it. Leave out anything they already bought or looked at.
  4. Rank with the hybrid score.

  Guests and brand-new shoppers get **Trending** instead.
- **"Why this?" chips:** short reasons on each card. At most two are shown, checked in this order:
  - *Same brand*
  - *Popular with shoppers like you*: many shoppers looked at both products; only the 3 strongest per strip get it
  - *Similar price*: within ±25%
  - *Top rated*: rating ≥ 4.5
  - *Trending*
  - *New arrival*: added in the last 30 days

  The personal feed says *Because you viewed X*.
- **"Frequently bought together"** on the cart page counts how many past orders contain both a cart item and another product ("Bought together ×2"). If there's no purchase history yet, it falls back to similar products.
- **"Recently viewed"** strips on the home and product pages use the session, so they work for guests too.

### Key design decisions
| Decision | Why |
|---|---|
| A weighted sum for the hybrid score | Easy to explain and tune. Each part is scaled to 0–1 first, so the weights mean what they say. |
| Log-scale popularity | One very popular product shouldn't squash everyone else's score close to 0. |
| Exponential recency decay | New arrivals get a fair chance, and the boost fades smoothly instead of switching off on a set day. |
| Taste vector = weighted average of feature vectors | Reuses the trained model. A purchase counts 3× a view, and old activity counts less. |
| Leave out things already bought or viewed | Recommendations should help you *discover*, not repeat your history. |
| Rule-based "Why this?" chips | Machine-learning scores are hard to explain to shoppers. Simple, true reasons build trust and are easy to defend in a viva. |
| Limit "shoppers like you" to the top 3 | With dense simulated data it was on every card, and a label on everything means nothing. |
| Frequently-bought-together counts orders, not quantities | Buying 5 pens in one order shouldn't count as 5 "together" purchases. |

### Likely viva questions
**Q: What is a hybrid recommender?**
A: One that combines several signals. Ours mixes *content similarity* (from the ML model) with *popularity* (what shoppers do) and *recency* (what's new). Pure similarity can recommend unpopular or out-of-date products; the mix balances this.

**Q: How does "Recommended for you" work for a new user?**
A: With no history we can't build a taste vector. That's the "cold start" problem. We show Trending (the most popular products this month) until they browse a few products.

**Q: What is content-based vs collaborative filtering? Which do you use?**
A:
- *Content-based* recommends items similar to ones you liked, using item features: our TF-IDF/K-Means model.
- *Collaborative* uses other users' behaviour: "people who bought X also bought Y".

We use **both**. The model is content-based. "Frequently bought together" and "Popular with shoppers like you" are collaborative signals.

**Q: Why does an old interaction count less?**
A: Tastes change. The weight halves every 30 days (`0.5 ** (age_days / 30)`), so last week's browsing matters more than last quarter's.

**Q: Could the weights be learned instead of hand-picked?**
A: Yes. You could try different weights and keep the ones with the best click-through rate. That's what the A/B test in Phase 6 starts to measure: plain similarity vs the hybrid ranking.

**Q: How is "Frequently bought together" calculated?**
A: Find every order that contains a product in your cart. Count, per other product, how many of those orders also contain it (`Count("order_id", distinct=True)`). Then sort by that count and leave out what's already in your cart.

---

## Phase 6: Admin dashboard, ML Insights and the A/B test

### What we built
- **Separate admin interface** at `/dashboard/` with its own sidebar layout. `dashboard/base_dashboard.html` extends `base.html` and swaps the shop navbar for a sidebar.
  - Guests are sent to log in. Logged-in customers get **403 Forbidden**. Only users with `role = admin` (or superusers) get in.
  - This is done with `admin_required` for function views and `StoreAdminRequiredMixin` for class-based views (`accounts/decorators.py`).
- **Overview:**
  - **KPI tiles:** revenue, orders, average order value, buyers and low stock, each compared with the previous 30 days.
  - **Charts:** revenue per day, orders per day, top products and revenue by category, drawn with **Chart.js**. Each has a "Show data table" option.
  - Order status counts and recent orders.
- **CRUD:** add, edit and delete products (with image upload) and categories using Django's generic class-based views. Orders get a status update (Placed → Shipped → Delivered), and the inventory page has a quick "add stock" form.
- **ML Insights:**
  - Model version, K, silhouette score, products × features, and a warning for products that aren't in the model yet.
  - **Elbow** and **silhouette** charts with the chosen K highlighted.
  - **PCA cluster maps** as 8 small panels, each highlighting one cluster.
  - **Click-through rate** for each recommendation strip.
  - The **A/B test** result with a statistical test.
  - A **Retrain model** button and an **A/B on/off switch**.
  - The data is labelled as simulated.
- **A/B test:** every shopper is put into group A or B by an MD5 hash of their user id (or guest session key).
  - **A** sees "You may also like" ranked by pure similarity.
  - **B** sees the hybrid ranking.

  Impressions and clicks record the group, so the CTRs can be compared.

### Key design decisions
| Decision | Why |
|---|---|
| Generic class-based views for CRUD | List, create, update and delete are the same pattern for every model. `ListView`/`CreateView` etc. give pagination, forms and redirects with very little code. |
| Products in past orders are hidden, not deleted | `OrderItem.product` is `on_delete=PROTECT`, so old orders keep their history. The admin sees a clear message instead of an error. |
| ORM aggregates (`Sum`, `Count`, `TruncDate`) for every number | The database does the maths with one query per chart instead of looping in Python. |
| One colour (teal) for every chart, grey for "other" | We ran the dataviz palette validator. Eight different colours can't be told apart reliably, especially by colour-blind readers. So each cluster gets its own small chart instead of one rainbow scatter. |
| A data table under every chart | Charts are images to a screen reader. The table makes every number available. |
| MD5 hash for A/B assignment | The same person always gets the same group (it's stable), and groups split about 50/50. Python's built-in `hash()` changes on every restart, so it can't be used. |
| Two-proportion z-test | It tells us whether B's CTR is *really* different from A's, or whether the gap could just be chance. |
| Shared `train_and_save()` | The command and the Retrain button run the exact same code, so they can't drift apart. |
| `next` URLs checked with `url_has_allowed_host_and_scheme` | Stops "open redirect" tricks that send admins to another website. |

### Bugs we found while testing (good viva stories)
- **Empty K-Means cluster:** products with identical text gave identical vectors, K-Means left a cluster empty, and ranking crashed. The fix is `members.get(cluster, [])`, and a test now covers it.
- **Windows clock resolution:** two orders and "now" got the *same* timestamp, because the Windows clock ticks about once per millisecond. The KPI window used `<` and left them out. The fix is an inclusive end (`<=`).
- **An invisible element widened the phone page:** the `visually-hidden` "Actions" heading is `position: absolute` and escaped its scrolling table. The fix is `position: relative` on the scroll container.

### Likely viva questions
**Q: How do you stop customers from opening the dashboard?**
A: Every dashboard view is wrapped with `admin_required` or `StoreAdminRequiredMixin`. A guest is redirected to the login page, and a customer gets HTTP 403. Tests check every dashboard page for all three kinds of user.

**Q: What is an A/B test?**
A: Show two versions to two random groups at the same time, measure the same metric (here CTR), and compare. Running both at once removes effects like "weekends are busier".

**Q: Explain the z-test you use.**
A: The pooled click rate is `p = (clicksA + clicksB) / (viewsA + viewsB)`.
- The standard error is `√(p(1−p)(1/nA + 1/nB))`.
- Then `z = (pB − pA) / SE`.
- The p-value is the chance of seeing a gap at least this big if A and B were truly equal.

If p < 0.05 we call the difference significant. Our simulated data gives p ≈ 0.25, so no real difference yet. That's expected, because the seed used the same click rate for both groups on purpose.

**Q: What is CTR and why measure it?**
A: Click-through rate = clicks ÷ impressions. It shows whether recommendations are useful to shoppers: a strip nobody clicks isn't helping.

**Q: What does the silhouette score mean?**
A: For each product, compare how close it is to its own cluster with how close it is to the nearest other cluster. It ranges from −1 to 1, and higher means better-separated clusters. Ours is 0.344 at K = 8.

**Q: Why do clusters overlap in the PCA picture if they're well separated?**
A: PCA keeps only the 2 strongest directions out of 332, about 20% of the variation here. Clusters separated along the other directions land on top of each other in a flat picture. The silhouette score is measured in the full space, so it's the real measure.

**Q: What happens when the admin clicks "Retrain model"?**
A:
1. JavaScript sends a POST with the CSRF token.
2. The view calls `train_and_save()`, which builds features, picks K, trains K-Means, ranks neighbours, saves `recomart_v{N+1}.joblib` and records a `TrainingRun`.
3. It resets the cached model.
4. The page reloads with the new metrics.

The next recommendation request uses the new version.

---

## Phase 7: Shopping assistant chatbot (offline)

### What we built
- **An "Ask RecoMart" chat button** on every shop page (not in the admin dashboard). It opens a small panel on desktop and a full-screen chat on phones.
- **It answers from the store's own data, with no internet or AI service:**
  - **Product search with filters:** "phones under 20k", "4 star books under 500", "cheapest shoes", "best rated perfume".
  - **Similar items:** "something like Atomic Habits", or "similar to this" on a product page. Uses our recommender.
  - **Personal picks:** "recommend something for me". Uses the "Recommended for you" feed.
  - **Today's deals.**
  - **Your latest order or a specific one** ("RM-000123"). Logged-in users only, and only their own orders.
  - **Your cart:** item count, total, and how much more you need for free delivery.
  - **FAQs:** delivery, payment, returns, and what RecoMart is.
  - **Greetings, thanks and help,** plus a polite fallback.
- **Every answer** is short text plus product rows, a link ("See all 12 results") and quick-reply chips.
- **The conversation survives page changes** (sessionStorage), and the reset button starts a new chat.

### How it understands a message
1. **Rules first, with regular expressions (`assistant/parser.py`):**
   - **Prices:** "under 20k", "below ₹2,500", "between 40000 and 60000".
   - **Ratings and sort words:** "4 star", "cheapest", "best rated".
   - **Order numbers** like RM-000123, and "like X".
   - **Product words map to categories:** "phones" → Electronics, "novel" → Books.
2. **Otherwise, nearest example phrase (`assistant/intents.py`).** Each intent has 6–12 example phrases.
   - The message and the examples become **TF-IDF vectors of character n-grams** (2–4 letters), and the intent of the most similar example by **cosine similarity** wins.
   - Character n-grams make typos like "wher is my ordr" still match.
   - If the best similarity is below 0.35, the answer is the **fallback**.
3. **The responder (`assistant/responder.py`) calls the store's existing services:**
   - `filter_products` for search
   - `similar_products` and `recommended_for` from the recommender
   - the cart service, and orders filtered by the logged-in user

### Key design decisions
| Decision | Why |
|---|---|
| Rules + TF-IDF nearest example instead of an AI API | It works offline, is free and fast, and every answer can be explained, just like the rest of the project. An AI model would need internet and an API key, and could make up products. |
| Reuse the store's own search and recommender | The chatbot can only show what the website itself would show. There's one search to maintain, not two. |
| Character n-grams, not words | Small spelling mistakes still share most 3-letter pieces with the correct word. |
| A synonym list at search time ("earbuds" → "airpod", "perfume" → "eau de") | Shoppers and catalogs use different words for the same thing. |
| Honest widening | If "gaming chair" isn't sold, it says so, instead of quietly showing unrelated products. |
| No memory between messages | Simpler and safer. Follow-up chips carry the full question: the button says "Best rated" but sends "phones under 20k best rated". |
| Orders filtered by `user=request.user` | Typing someone else's order number can never reveal their details. A test checks this. |
| 20 messages per minute per visitor, 500-character limit | Stops a script from flooding the server. |
| Answers drawn with `textContent`, not `innerHTML` | Nothing typed by a user or stored in the database can inject HTML or scripts (XSS). |

### Likely viva questions
**Q: Is this an AI chatbot like ChatGPT?**
A: No. It's a **retrieval-based** chatbot: it works out the *intent* of the message, then looks up real data. It can't write free-form answers, but it never invents products or prices, and it works offline.

**Q: How does it decide what the user wants?**
A:
1. Rules (regular expressions) catch clear patterns: order numbers, "like X", prices and ratings.
2. Otherwise, TF-IDF turns the message and about 100 example phrases into vectors, and the intent of the most similar example by cosine similarity wins.
3. If even the best match scores below 0.35, it says it didn't understand and offers suggestions.

**Q: Why character n-grams?**
A: "order" and "ordr" share the pieces "or" and "rd", while the whole words don't match at all. So typos still work.

**Q: How do you stop it showing someone else's order?**
A: The order lookup always starts from `Order.objects.filter(user=request.user)`. Guests are asked to log in. A test types another user's order number and checks that nothing is shown.

**Q: How is it protected?**
A:
- It accepts POST only, protected by Django's CSRF check like every form.
- Messages are limited to 500 characters.
- There's a rate limit of 20 messages per minute per session, kept in Django's cache.
- Replies are drawn with `textContent`, never `innerHTML`, so there's no XSS.

**Q: How would you make it smarter?**
A:
- Add more example phrases, or learn new ones from messages that hit the fallback.
- Train a small classifier, such as logistic regression on the same TF-IDF features, instead of nearest example.
- Or plug in a language model for free-form answers, keeping our search as its only source of facts.
