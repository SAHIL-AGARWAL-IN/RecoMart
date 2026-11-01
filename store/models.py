from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    icon = models.CharField(max_length=40, default="bag", help_text="Bootstrap Icons name, e.g. 'laptop'")
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("store:category", args=[self.slug])


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         help_text="Sale price. Leave empty when there is no discount.")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to="products/", blank=True)
    stock = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    # Filled by `train_recommender`: the product's ML feature vector.
    feature_vector = models.JSONField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    # A default (not auto_now_add) so seed data can spread products over past months.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("store:product_detail", args=[self.slug])

    def clean(self):
        if self.discount_price is not None and self.price and self.discount_price >= self.price:
            raise ValidationError({"discount_price": "Discount price must be lower than the price."})

    @property
    def effective_price(self):
        """The price the customer actually pays."""
        return self.discount_price if self.discount_price is not None else self.price

    @property
    def discount_percent(self):
        if self.discount_price is None or not self.price:
            return 0
        return int(round((1 - self.discount_price / self.price) * 100))

    @property
    def in_stock(self):
        return self.stock > 0

    def update_rating(self):
        """Recalculate the average rating from reviews (called whenever a review changes)."""
        stats = self.reviews.aggregate(avg=Avg("rating"), count=Count("id"))
        self.rating_avg = round(Decimal(stats["avg"] or 0), 2)
        self.rating_count = stats["count"]
        self.save(update_fields=["rating_avg", "rating_count", "updated_at"])


class ProductImage(models.Model):
    """Extra gallery images. The main image stays on Product.image."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.product.name} image {self.sort_order}"


class Interaction(models.Model):
    """One shopper action on a product. This is the behaviour data the recommender learns from."""

    class Type(models.TextChoices):
        VIEW = "view", "Viewed"
        CART = "cart", "Added to cart"
        WISHLIST = "wishlist", "Wishlisted"
        PURCHASE = "purchase", "Purchased"
        REVIEW = "review", "Reviewed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="interactions")
    session_key = models.CharField(max_length=40, blank=True, db_index=True,
                                   help_text="Identifies guests, who have no user account.")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="interactions")
    interaction_type = models.CharField(max_length=10, choices=Type.choices)
    quantity = models.PositiveSmallIntegerField(default=1)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["product", "interaction_type"]),
            models.Index(fields=["user", "timestamp"]),
        ]

    def __str__(self):
        who = self.user or f"guest:{self.session_key[:6]}"
        return f"{who} {self.interaction_type} {self.product}"


class Cart(models.Model):
    """A shopping cart. Logged-in users own one by `user`; guests by their session key."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                related_name="cart")
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart of {self.user or 'guest'}"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.select_related("product")), Decimal("0"))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [models.UniqueConstraint(fields=["cart", "product"], name="unique_product_per_cart")]

    def __str__(self):
        return f"{self.quantity} x {self.product}"

    @property
    def line_total(self):
        return self.product.effective_price * self.quantity


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"

    class PaymentMethod(models.TextChoices):
        UPI = "upi", "UPI (simulated)"
        CARD = "card", "Card (simulated)"
        COD = "cod", "Cash on delivery"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLACED)
    # Shipping details
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15)
    address_line = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    pincode = models.CharField(max_length=6)
    # Payment (simulated: no real gateway is contacted)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    payment_ref = models.CharField(max_length=40, blank=True, help_text="Fake transaction id, e.g. SIM-8F2K1Q")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    @property
    def order_number(self):
        return f"RM-{self.pk:06d}" if self.pk else "RM-new"

    def get_absolute_url(self):
        return reverse("store:order_detail", args=[self.pk])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    # Snapshots: the order must not change if the product is renamed or repriced later.
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="one_review_per_user_product")]

    def __str__(self):
        return f"{self.rating}★ {self.product} by {self.user}"

    # Keep Product.rating_avg in sync. Ratings are also an ML feature, so they feed the recommender.
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.product.update_rating()

    def delete(self, *args, **kwargs):
        product = self.product
        result = super().delete(*args, **kwargs)
        product.update_rating()
        return result


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-added_at"]
        constraints = [models.UniqueConstraint(fields=["user", "product"], name="unique_wishlist_item")]

    def __str__(self):
        return f"{self.user} ♥ {self.product}"
