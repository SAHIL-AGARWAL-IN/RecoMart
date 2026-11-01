from django.urls import path

from . import api, views

app_name = "store"

urlpatterns = [
    # Pages
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("category/<slug:slug>/", views.product_list, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("product/<slug:slug>/review/", views.submit_review, name="submit_review"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/thank-you/", views.order_success, name="order_success"),
    # JSON API, called with fetch() from the page's JavaScript
    path("api/cart/add/", api.cart_add, name="api_cart_add"),
    path("api/cart/update/", api.cart_update, name="api_cart_update"),
    path("api/cart/remove/", api.cart_remove, name="api_cart_remove"),
    path("api/wishlist/toggle/<int:product_id>/", api.wishlist_toggle, name="api_wishlist_toggle"),
    path("api/search/", api.search, name="api_search"),
    path("api/products/", api.products, name="api_products"),
]
