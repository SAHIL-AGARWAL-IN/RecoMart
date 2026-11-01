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
