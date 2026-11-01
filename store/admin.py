from django.contrib import admin
from django.utils.html import format_html

from .models import (Cart, CartItem, Category, Interaction, Order, OrderItem, Product, ProductImage, Review,
                     WishlistItem)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "sort_order", "product_count")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "name", "category", "brand", "price", "discount_price", "stock", "rating_avg",
                    "is_active")
    list_display_links = ("thumbnail", "name")
    list_filter = ("category", "is_active", "brand")
    list_editable = ("stock", "is_active")
    search_fields = ("name", "brand", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("rating_avg", "rating_count", "created_at", "updated_at")
    list_select_related = ("category",)
    inlines = [ProductImageInline]

    @admin.display(description="")
    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" alt="" style="height:40px;width:40px;object-fit:cover;'
                               'border-radius:6px">', obj.image.url)
        return "-"


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "session_key", "interaction_type", "product", "quantity")
    list_filter = ("interaction_type",)
    search_fields = ("product__name", "user__username", "session_key")
    list_select_related = ("user", "product")
    date_hierarchy = "timestamp"


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ("product",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "updated_at")
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    raw_id_fields = ("product",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "payment_method", "total", "created_at")
    list_filter = ("status", "payment_method")
    list_editable = ("status",)
    search_fields = ("id", "user__username", "full_name", "city")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    inlines = [OrderItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("product__name", "user__username", "comment")
    list_select_related = ("product", "user")


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "added_at")
    list_select_related = ("user", "product")
