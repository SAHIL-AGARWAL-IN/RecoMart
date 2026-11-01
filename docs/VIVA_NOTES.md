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
