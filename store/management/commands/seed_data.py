"""python manage.py seed_data [--fresh] [--offline] [--seed 42] [--users 40]

Creates the demo store: 8 categories, ~150 products with photos, customers and SIMULATED
behaviour (views, carts, wishlists, orders, reviews, recommendation clicks) so that the
recommender and the dashboard charts have realistic data to work with.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from recommender.models import RecommendationData, RecommendationEvent, TrainingRun
from store.models import (Cart, Category, Interaction, Order, Product, ProductImage, Review, WishlistItem)
from store.seed import images
from store.seed.catalog import CATEGORIES, build_catalog, discounted_price
from store.seed.photos import ensure_images
from store.seed.shoppers import ShopperSimulator

User = get_user_model()

DEMO_ADMIN = {"username": "admin", "password": "Admin@123", "first_name": "Store", "last_name": "Admin"}
DEMO_CUSTOMER = {"username": "priya", "password": "Customer@123", "first_name": "Priya", "last_name": "Sharma",
                 "preferred": ["electronics", "books"]}
CUSTOMER_PASSWORD = "Customer@123"
MAX_GALLERY_IMAGES = 3
# About 15% of products get a big sale (25-50% off) so "Today's deals" stands out.
BIG_SALE_SHARE = 0.15
BIG_SALE_RANGE = (25, 50)


class Command(BaseCommand):
    help = "Seed the database with a demo catalog and SIMULATED shoppers, orders, reviews and interactions."

    def add_arguments(self, parser):
        parser.add_argument("--fresh", action="store_true", help="Delete existing store data first.")
        parser.add_argument("--offline", action="store_true",
                            help="Do not download photos; use cached files or generated images.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed, for reproducible data.")
        parser.add_argument("--users", type=int, default=40, help="Number of simulated customers.")
        parser.add_argument("--guests", type=int, default=60, help="Number of simulated guest visitors.")

    def handle(self, *args, **options):
        if Product.objects.exists() and not options["fresh"]:
            raise CommandError("The database already has products. Run with --fresh to rebuild it.")

        rng = random.Random(options["seed"])
        Faker.seed(options["seed"])
        fake = Faker("en_IN")

        if options["fresh"]:
            self._wipe()

        self.stdout.write("Creating categories and products...")
        with transaction.atomic():
            categories = self._create_categories()
            specs = build_catalog(offline=options["offline"])
            products = self._create_products(specs, categories, rng)

        self.stdout.write(f"Preparing images for {len(products)} products (first run downloads them)...")
        image_stats = self._attach_images(products, specs, options["offline"])

        self.stdout.write("Simulating shoppers, orders and reviews...")
        with transaction.atomic():
            admin, customers = self._create_users(fake, rng, options["users"])
            base_ratings = {p.id: spec["base_rating"] for p, spec in zip(products, specs)}
            sim = ShopperSimulator(rng, fake, products, base_ratings)

            priya = next(u for u in customers if u.username == DEMO_CUSTOMER["username"])
            sim.simulate_customer(priya, DEMO_CUSTOMER["preferred"], sessions=16)
            for user in customers:
                if user is not priya:
                    preferred = rng.sample(sim.category_slugs, 2)
                    sim.simulate_customer(user, preferred, sessions=rng.randint(3, 14))
            for _ in range(options["guests"]):
                sim.simulate_guest(sessions=rng.randint(1, 3))
            sim.top_up_reviews(customers)
            sim.calibrate_ratings()

            Interaction.objects.bulk_create(sim.interactions, batch_size=1000)
            WishlistItem.objects.bulk_create(sim.wishlist, batch_size=1000)
            Review.objects.bulk_create(sim.reviews, batch_size=1000)
            RecommendationEvent.objects.bulk_create(sim.simulate_rec_events(customers), batch_size=1000)
            # bulk_create skips Review.save(), so refresh the average ratings once here.
            for product in products:
                product.update_rating()

        self._print_summary(sim, image_stats)

    # ------------------------------------------------------------------ steps
    def _wipe(self):
        self.stdout.write("Removing existing store data...")
        with transaction.atomic():
            for model in (RecommendationEvent, RecommendationData, TrainingRun, Interaction, Review, WishlistItem,
                          Cart, Order, ProductImage, Product, Category):
                model.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            User.objects.filter(username=DEMO_ADMIN["username"]).delete()

    def _create_categories(self):
        return {
            row["slug"]: Category.objects.create(sort_order=index, **row)
            for index, row in enumerate(CATEGORIES)
        }

    def _apply_big_sales(self, specs, rng):
        for spec in rng.sample(specs, k=round(len(specs) * BIG_SALE_SHARE)):
            spec["discount_price"] = discounted_price(spec["price"], rng.uniform(*BIG_SALE_RANGE))

    def _create_products(self, specs, categories, rng):
        self._apply_big_sales(specs, rng)
        used_slugs, products = set(), []
        now = timezone.now()
        for spec in specs:
            slug = base = slugify(spec["name"])[:200]
            counter = 2
            while slug in used_slugs:
                slug, counter = f"{base}-{counter}", counter + 1
            used_slugs.add(slug)
            products.append(Product(
                name=spec["name"], slug=slug, description=spec["description"], brand=spec["brand"],
                category=categories[spec["category"]], price=spec["price"],
                discount_price=spec["discount_price"], stock=spec["stock"],
                created_at=now - timedelta(days=rng.uniform(0, 180)),
            ))
        Product.objects.bulk_create(products)
        # Re-read so every product has its id and its category loaded.
        by_slug = {p.slug: p for p in Product.objects.select_related("category")}
        return [by_slug[p.slug] for p in products]

    def _attach_images(self, products, specs, offline):
        jobs, gallery = [], []
        for product, spec in zip(products, specs):
            main_path = f"products/{product.slug}.webp"
            urls = spec["image_urls"]
            if spec["image_kind"] == "book":
                fallback = lambda p=product: images.book_cover(p.name, p.brand)
            elif spec["image_kind"] == "toy":
                fallback = lambda p=product: images.toy_image(p.name)
            else:
                fallback = lambda p=product: images.placeholder(p.name, p.category.name)
            jobs.append({"path": main_path, "url": urls[0] if urls else None, "fallback": fallback})
            for index, url in enumerate(urls[1:MAX_GALLERY_IMAGES + 1], start=1):
                path = f"products/gallery/{product.slug}-{index}.webp"
                jobs.append({"path": path, "url": url})
                gallery.append((product, path, index))

        statuses = ensure_images(jobs, offline=offline)

        for product in products:
            product.image.name = f"products/{product.slug}.webp"
        Product.objects.bulk_update(products, ["image"])
        ProductImage.objects.bulk_create([
            ProductImage(product=product, image=path, alt_text=f"{product.name}, view {index + 1}", sort_order=index)
            for product, path, index in gallery if statuses[path] != "skipped"
        ])

        stats = {}
        for status in statuses.values():
            stats[status] = stats.get(status, 0) + 1
        return stats

    def _create_users(self, fake, rng, count):
        admin = User.objects.create_superuser(
            username=DEMO_ADMIN["username"], email="admin@recomart.test", password=DEMO_ADMIN["password"],
            first_name=DEMO_ADMIN["first_name"], last_name=DEMO_ADMIN["last_name"], role=User.Role.ADMIN,
        )
        # Hash the shared demo password once instead of 40 times (hashing is deliberately slow).
        hashed = make_password(CUSTOMER_PASSWORD)
        now = timezone.now()
        people = [(DEMO_CUSTOMER["first_name"], DEMO_CUSTOMER["last_name"], DEMO_CUSTOMER["username"])]
        used = {DEMO_CUSTOMER["username"], DEMO_ADMIN["username"]}
        while len(people) < max(count, 1):
            first, last = fake.first_name(), fake.last_name()
            username = slugify(f"{first}{last[:1]}{rng.randint(10, 99)}").replace("-", "")
            if username and username not in used:
                used.add(username)
                people.append((first, last, username))
        User.objects.bulk_create([
            User(username=username, first_name=first, last_name=last, email=f"{username}@example.com",
                 password=hashed, role=User.Role.CUSTOMER,
                 date_joined=now - timedelta(days=rng.uniform(95, 365)))
            for first, last, username in people
        ])
        customers = list(User.objects.filter(role=User.Role.CUSTOMER).order_by("id"))
        return admin, customers

    def _print_summary(self, sim, image_stats):
        ok = self.style.SUCCESS
        self.stdout.write(ok("\nSeed complete."))
        rows = [
            ("Categories", Category.objects.count()),
            ("Products", Product.objects.count()),
            ("Out of stock", Product.objects.filter(stock=0).count()),
            ("Customers", User.objects.filter(role=User.Role.CUSTOMER).count()),
            ("Orders", Order.objects.count()),
            ("Reviews", Review.objects.count()),
            ("Wishlist items", WishlistItem.objects.count()),
            ("Interactions", Interaction.objects.count()),
            ("Rec. events", RecommendationEvent.objects.count()),
        ]
        for label, value in rows:
            self.stdout.write(f"  {label:<15}{value:>7}")
        self.stdout.write("  Images         " + ", ".join(f"{k}: {v}" for k, v in sorted(image_stats.items())))
        self.stdout.write(self.style.WARNING(
            "  Note: users, orders, reviews and interactions are SIMULATED demo data."))
        self.stdout.write("\nDemo logins:")
        self.stdout.write(f"  Admin     {DEMO_ADMIN['username']} / {DEMO_ADMIN['password']}")
        self.stdout.write(f"  Customer  {DEMO_CUSTOMER['username']} / {DEMO_CUSTOMER['password']}")
        self.stdout.write("\nNext: python manage.py train_recommender")
