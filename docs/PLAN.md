# RecoMart: build plan

> This is the source of truth for the build. After a `/clear`, read this file and `CLAUDE.md`, find the first unchecked phase below, and continue from there.

## Phase status
- [x] Phase 1: Foundation (setup, apps, models, migrations, Django admin, seed data), branch `phase-1-foundation` (done, merged into `main`)
- [x] Phase 2: Storefront UI (base.html, theme, auth pages, home, product list, product detail), branch `phase-2-storefront` (done, merged into `main`)
- [ ] Phase 3: Shopping (cart, checkout, orders, wishlist, reviews, AJAX search & filters)
- [ ] Phase 4: ML engine (features, training command, Joblib, recommendation API, "You may also like")
- [ ] Phase 5: Enhancements (personalised feed, hybrid ranking, explanations, FBT, recently viewed)
- [ ] Phase 6: Admin dashboard, ML Insights, A/B toggle
- [ ] Phase 7: Polish (dark mode, responsiveness, tests, README)

Each phase ends with:
- check, tests and Playwright screenshots all green
- a new section in `docs/VIVA_NOTES.md`
- this checklist updated
- a stop so the user can test; after their approval the branch is fast-forwarded into `main`

## Context
RecoMart is a B.Tech CSE Sem-5 Full Stack Lab project for a team of 4. It is a Django e-commerce store with a built-in scikit-learn recommendation engine. The stack in the approved synopsis is fixed. The code has to look professional in a demo and be easy for the students to explain in a viva. The tools on the dev machine are Python 3.12 (venv), git and Node. Playwright MCP is available for screenshots.

**Decisions made with the user**
- Currency is **₹ INR** with Indian digit grouping (₹1,29,999) and timezone Asia/Kolkata.
- Catalog: real products from the free **DummyJSON** API, fetched once by `seed_data` and cached locally. It has 194 products in 24 categories, `.webp` studio photos, and prices in USD that get converted to INR. It has **no books or toys**, so I write those products myself and generate cover-style images for them.
- The demo has to work **offline**. Bootstrap, Bootstrap Icons, Chart.js and the fonts (Plus Jakarta Sans, Inter) are saved in `static/vendor/`. This differs from "Chart.js (CDN)" and the README will say so.

**My calls (flag any you disagree with)**
- **Python 3.12** for the venv (`py -3.12 -m venv .venv`). 3.14 is the system default, but Django 5.2 LTS, scikit-learn and NumPy all have proven 3.12 wheels.
- **Django 5.2 LTS**.
- A **custom user model** `accounts.User(AbstractUser)` with a `role` field (Customer/Admin). Django has to know about it before the first migration, and it is cleaner than a Profile model.
- **Guest carts are allowed.** A cart is keyed by `session_key` and merged into the user's cart on login. Wishlist, reviews and checkout require login.
- **Simulated payment** offers UPI, Card or COD. A card number only gets a format/Luhn check and is never stored; only the last 4 digits and a fake `SIM-…` transaction id are kept. The page says "Demo payment – don't use real card details".
- **Recommendation measurement uses its own model, `RecommendationEvent`** (impression/click × widget × A/B variant). `Interaction` stays the shopper-behaviour data the model trains on, and click-through rate (CTR) = clicks ÷ impressions.
- **Git:** `main`, plus one branch per phase (`phase-1-foundation`, …). I commit after every working step and fast-forward the branch into `main` after you've tested the phase.
- Views: **function-based views** for the storefront and the APIs, **generic class-based views** for dashboard CRUD. Both are standard Django and both are easy to explain.

---

**Additions after approval (user)**
- This plan is saved as `docs/PLAN.md`, with a phase-status checklist, and `CLAUDE.md` points to it. That way any session can pick up after `/clear`.
- The DummyJSON response cache is committed (`store/seed/dummyjson_products.json`) but the images are not. The README notes that the first seed needs internet for the images.
- At the end of each phase, `docs/VIVA_NOTES.md` gets a section covering what was built, the key design decisions, and likely viva questions with simple answers (Sem-5 level).
- Interaction data is labelled as **simulated by seed_data** in the README and on the ML Insights page.

## Folder structure
```
RecoMart/  (repo root = E:\Projects\Recommendation system)
├── manage.py  requirements.txt  .env.example  .gitignore  CLAUDE.md  README.md
├── config/                  settings.py (dotenv, SQLite|Postgres via env), urls.py, wsgi.py, asgi.py
├── accounts/                User model (+role), forms, views (register/login/logout/profile),
│                            decorators.py (admin_required, StoreAdminRequiredMixin), signals.py (merge cart on login)
├── store/
│   ├── models.py            Category, Product, ProductImage, Interaction, Cart, CartItem,
│   │                        Order, OrderItem, Review, WishlistItem
│   ├── cart.py              cart service (get/add/update/remove/merge/totals)
│   ├── services.py          checkout (atomic order + stock), interaction logging, trending, recently-viewed
│   ├── views.py  api.py     pages / JSON endpoints (search, filters, cart, wishlist)
│   ├── forms.py  context_processors.py  templatetags/store_tags.py (₹ format, stars)
│   ├── seed/                books_toys.py (hand-written catalog), images.py (Pillow cover generator)
│   └── management/commands/seed_data.py
├── recommender/
│   ├── features.py          product DataFrame → feature matrix (TF-IDF, one-hot, scaled numerics)
│   ├── engine.py            train (K choice, KMeans), similarity, hybrid ranking, personalize,
│   │                        explain chips, save/load (Joblib), cached singleton
│   ├── services.py          DB glue: A/B variant, impressions/clicks, frequently-bought-together, popularity
│   ├── models.py            RecommendationData, TrainingRun, RecommendationEvent
│   ├── api.py  urls.py      /api/recommendations/...
│   ├── artifacts/           recomart_v{N}.joblib (git-ignored, .gitkeep)
│   └── management/commands/train_recommender.py
├── dashboard/               views.py (KPIs, CRUD CBVs, ML insights, retrain), forms.py, analytics.py (aggregates)
├── templates/
│   ├── base.html            root layout; blocks: title, extra_head, navbar, content, footer, extra_js
│   ├── partials/            _navbar, _footer, _product_card, _stars, _toasts, _pagination,
│   │                        _empty_state, _skeleton_cards, _rec_carousel
│   ├── accounts/  store/    login, register, profile / home, product_list, product_detail, cart,
│   │                        checkout, order_list, order_detail, order_success, wishlist
│   ├── dashboard/           base_dashboard.html (extends base, swaps navbar for sidebar), index,
│   │                        product_*, category_*, order_*, inventory, ml_insights
│   └── 404.html  500.html
├── static/
│   ├── css/theme.css  css/dashboard.css
│   ├── js/main.js (CSRF fetch helper, toasts, cart badge, theme toggle)  search.js  filters.js
│   │      wishlist.js  recommendations.js  dashboard.js  ml_insights.js
│   ├── img/                 logo.svg, favicon, empty-state illustrations (SVG)
│   └── vendor/              bootstrap 5.3.x, bootstrap-icons 1.11.x, chart.js 4.x, fonts (woff2)
├── media/                   uploaded and seeded product images (git-ignored)
└── docs/screenshots/        Playwright captures used in README
```

## Data model (summary)
- **User**: AbstractUser + `role` (customer|admin). The `is_store_admin` property is true for role=admin or a superuser.
- **Category**: name, slug, icon (Bootstrap Icon name), description, sort_order.
- **Product**: name, slug, description, price, discount_price?, category, brand, image, stock, rating_avg, rating_count, `feature_vector` (JSON), is_active, created_at. It has `effective_price`, `discount_percent` and `in_stock` helpers.
- **ProductImage**: product, image, sort_order. Feeds the gallery; DummyJSON has 1–4 images per product.
- **Interaction**: user?, session_key, product, type (view|cart|wishlist|purchase|review), quantity, timestamp. Indexed on (product, type) and (user, timestamp).
- **Cart**: user? and session_key. **CartItem**: unique (cart, product); quantity is capped by stock.
- **Order**: user, status (placed→shipped→delivered), shipping fields, payment_method, payment_ref, total, created_at. **OrderItem** keeps a snapshot of `unit_price`.
- **Review**: user, product, rating 1–5 (validators), comment. Unique per (user, product), and saving one recomputes the product's rating.
- **WishlistItem**: user, product, unique together.
- **RecommendationData**: product (1–1), cluster_id, similar_ids, similar_scores, model_version.
- **TrainingRun**: version, k, silhouette, per-k inertia and silhouette tables, n_products, n_features, trained_at, duration.
- **RecommendationEvent**: user?, session_key, widget (similar|for_you|trending|fbt), variant (A|B), event (impression|click), product, source_product?, created_at.

## ML pipeline (`recommender/features.py` + `engine.py`)
1. **Data:** active products from the ORM go into a Pandas DataFrame, together with 90-day interaction counts per type and rating_avg.
2. **Features:** a `ColumnTransformer` builds the vector from:
   - TF-IDF of name + brand + category + description (≈300 terms, English stop words)
   - one-hot category
   - one-hot brand (rare brands → "other")
   - MinMax-scaled log(price), rating and log1p(interaction counts)
   
   Each block gets a weight from `transformer_weights`, and every row is then L2-normalised so that the dot product equals cosine similarity. The vectors are also written to `Product.feature_vector`.
3. **Choosing K:** KMeans (n_init=10, random_state=42) runs for k = 3…12. For each k it logs inertia (the elbow; the "knee" is found by maximum distance to the chord) and the silhouette score. K = best silhouette, and `--k` can override it.
4. **Similarity:** the cosine matrix gives each product its top-20 within its own cluster. Free slots are filled from the nearest clusters by centroid distance. A product never recommends itself. The results are cached in the `RecommendationData` rows.
5. **Persistence:** Joblib dumps `{version, pipeline, kmeans, product_ids, matrix, topN, pca_2d, metrics}` to `recommender/artifacts/recomart_v{N}.joblib`. A `TrainingRun` row records the run.
6. **Serving:** the newest model is loaded lazily once per process and kept as a cached singleton. Retraining resets it. Out-of-stock items are multiplied by a penalty and sink to the end. A product added after training falls back to same-category trending items until the next retrain, and the dashboard flags the model as stale.
7. **Hybrid score:** `w_sim·similarity + w_pop·popularity + w_rec·recency`.
   - popularity = log-normalised, type-weighted interactions over 30 days
   - recency = exp(−days since added / 90)
   - The weights live in `settings.RECOMMENDER`. The starting values are 0.6 / 0.25 / 0.15.
8. **Personalised feed:** the user's last ~20 interactions are weighted by type (purchase 3, cart/wishlist 2, view 1) and by recency, then averaged into one vector. That vector gets cosine similarity against every product, already-purchased items are removed, and the hybrid score ranks the rest. Guests and new users get Trending.
9. **"Why this?" chips:** each card shows at most 2 rule-based reasons: *Same brand*, *Same category*, *Similar price* (±25%), *Top rated*, *Popular with shoppers like you* (co-interaction among users who touched the source item), *Trending*, *New arrival*. The personalised feed also uses *Because you viewed X*.
10. **Frequently bought together:** co-purchase counts from OrderItem, using orders that contain the cart's products and excluding items already in the cart. It falls back to similar items.
11. **A/B test:** a stable MD5 hash of user id or session key picks the variant. A = pure similarity, B = hybrid. It applies to the "You may also like" widget and can be switched off with `AB_TEST_ENABLED`.

`python manage.py train_recommender [--k N] [--k-min/--k-max]` prints:
- dataset size and missing values per column
- matrix shape and a NaN check
- the k table (inertia, silhouette) and the chosen K
- cluster sizes
- sample recommendations for 3 products
- the saved path and version

## URL map
| Area | URLs |
|---|---|
| Storefront | `/`, `/products/`, `/category/<slug>/`, `/product/<slug>/`, `/cart/`, `/checkout/`, `/orders/`, `/orders/<id>/`, `/wishlist/` |
| Accounts | `/accounts/register/`, `/login/`, `/logout/` (POST), `/profile/` |
| Store APIs (JSON) | `/api/search/?q=` (dropdown data), `/api/products/?q&category&min_price&max_price&min_rating&sort&page` (`{count, html, has_next}`), `/api/cart/add|update|remove/`, `/api/wishlist/toggle/<id>/`, `/product/<slug>/review/` |
| Recommender APIs | `/api/recommendations/<product_id>/`, `/api/recommendations/for-you/`, `/trending/`, `/frequently-bought/` |
| Dashboard (admin role) | `/dashboard/`, `/dashboard/products/…` (CRUD), `/categories/…`, `/orders/…` (status update), `/inventory/`, `/ml/`, `/ml/retrain/` (POST) |
| Django admin | `/admin/` |

Clicks on recommendations are tracked through `?rec=<widget>&v=<variant>` on the product link. The product view logs the click. The API logs impressions in bulk when it serves results.

## Design direction (finalised in Phase 2 with the frontend-design skill)
Tentative brand: a deep teal primary, a marigold/saffron accent for deals and badges, and warm neutral grays. Headings use Plus Jakarta Sans and body text uses Inter. Every colour, radius, shadow and spacing value is a CSS custom property in `theme.css`, and Bootstrap's `--bs-*` variables are overridden from there. Both light and dark token sets are defined from day one through `[data-bs-theme]`. Target AA contrast.

## Phases (I stop after each one for you to test)
**Phase 1: Foundation**
1. `git init -b main`, `.gitignore`, venv, pinned `requirements.txt`, `.env.example` and `.env`, `CLAUDE.md`.
2. `django-admin startproject config .` and the 4 apps. Settings cover dotenv, `DATABASE_URL`-style Postgres support, INR/IST, static/media, `AUTH_USER_MODEL` and the `RECOMMENDER` dict.
3. All models, migrations, and Django admin set up with list_display, filters, search and inlines.
4. `seed_data [--fresh] [--offline] [--seed 42]`:
   - Fetch DummyJSON and keep up to ~22 products per category, mapped to our 8 categories (vehicle and motorcycle dropped).
   - Convert USD→INR into ₹…99 price points.
   - Fill missing brands (groceries, kitchen) with sensible house brands.
   - Download images into `media/` once and reuse them on later runs.
   - Add hand-written books and toys with Pillow-generated covers.
   - Create about 40 Faker `en_IN` users with 2 preferred categories each, so the behaviour has real structure.
   - Spread views, carts, wishlists, orders (all 3 statuses), reviews and recommendation events over 90 days.
   - Print the demo logins.
   - `--offline` with no cache falls back to generated images.
5. Tests: model helpers, review→rating recompute, seed smoke test (offline, small fixture).

**Phase 2: Storefront UI**
- Vendor the assets.
- Theme and `base.html` with its partials.
- Auth pages.
- Home page: hero with search, category tiles, Trending, deal cards, and a "Recommended for You" slot that gets wired up in Phase 5.
- Product list and category pages (server-rendered filters for now).
- Product detail page: gallery, sticky buy box, description/reviews tabs, and a slot for "You may also like".
- Logging of view interactions and the session list of recently viewed items.

**Phase 3: Shopping**
- Cart service with guest carts and merge on login.
- AJAX add-to-cart with a toast and a live cart badge.
- Cart page.
- Checkout with simulated payment, using `transaction.atomic` and F-expression stock decrements.
- Order history, detail and success pages.
- AJAX wishlist heart.
- Reviews, one per user.
- Live search dropdown: 300 ms debounce, AbortController, thumbnails.
- AJAX filters, sort and pagination, with the URL kept in sync.

**Phase 4: ML engine**
- `features.py`, `engine.py` and the `train_recommender` command with full diagnostics.
- Versioned Joblib files, `TrainingRun` and `RecommendationData`.
- Cached loader.
- `/api/recommendations/<id>/`.
- "You may also like" scroll carousel with skeleton loaders.
- Impression and click logging.

**Phase 5: Enhancements**
- Personalised "Recommended for You" (Trending for guests).
- Hybrid ranking.
- "Why this?" chips.
- Frequently bought together on the cart page.
- Recently viewed strip on the home and product pages.

**Phase 6: Admin dashboard**
- Sidebar layout.
- KPI cards: revenue, orders, customers, AOV (average order value), low stock.
- Chart.js charts: revenue/orders over 30 days, top products, category split, order status.
- CRUD for products (image upload) and categories.
- Orders with status changes.
- Inventory page with quick restock.
- **ML Insights:**
  - PCA 2-D scatter coloured by cluster, with product-name tooltips
  - elbow and silhouette charts
  - K, silhouette, version, last trained, and a stale-model warning
  - a **Retrain** button that runs training via `fetch` and shows the new metrics live
  - CTR per widget
  - A/B CTR comparison with a two-proportion z-test

**Phase 7: Polish**
- Dark/light toggle stored in localStorage, with an inline head script so the page doesn't flash.
- Responsive and accessibility pass on every page: skip link, focus-visible, aria-live toasts, labels and alt text.
- Empty-state illustrations and 404/500 pages.
- Query tuning (`select_related`/`prefetch_related`).
- Full test run and a code review.
- `README.md`: Windows setup, seeding, training, demo logins, screenshots, and a viva-ready explanation of the ML pipeline.

## Verification (every phase)
- `python manage.py check`, `makemigrations --check --dry-run` and `python manage.py test` all pass. Failures get fixed before the phase stops, and I'll report the output exactly as it is.
- Run the dev server and drive it with **Playwright MCP** at 375, 768 and 1280 px. Take screenshots, check the console for errors, critique the result and fix it.
- Tests are written alongside the code. Cart, checkout and the recommender are written test-first.
- **Recommender tests** run on a small deterministic fixture with a temporary `ARTIFACTS_DIR`. They check that:
  - no product recommends itself
  - the top match shares the category
  - out-of-stock items rank last
  - a Joblib reload gives identical output
  - vectors contain no NaNs
  - personalisation excludes purchased items
  - frequently-bought-together counts are correct
  - A/B assignment is stable
  - the chips are correct
- **Other tests check that:**
  - the role guard blocks customers from the dashboard
  - checkout creates the order, decrements stock and clears the cart
  - the search and filter APIs return the right JSON
- **Phase 4 printout:** dataset size, missing values, vector shape, the NaN check, K and its silhouette score, and cluster sizes.

## Windows commands you'll use
```powershell
py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1   # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python manage.py migrate ; python manage.py seed_data ; python manage.py train_recommender
python manage.py runserver   # http://127.0.0.1:8000  (admin: /dashboard/)
python manage.py test
```
Demo logins (printed by seed and listed in the README): `admin / Admin@123` (admin role, superuser) and `priya / Customer@123`, a customer with an existing purchase history so "Recommended for You" is filled in right away.
