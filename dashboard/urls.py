from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("products/", views.ProductListView.as_view(), name="products"),
    path("products/new/", views.ProductCreateView.as_view(), name="product_add"),
    path("products/<int:pk>/edit/", views.ProductUpdateView.as_view(), name="product_edit"),
    path("products/<int:pk>/delete/", views.ProductDeleteView.as_view(), name="product_delete"),
    path("categories/", views.CategoryListView.as_view(), name="categories"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category_add"),
    path("categories/<int:pk>/edit/", views.CategoryUpdateView.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", views.CategoryDeleteView.as_view(), name="category_delete"),
    path("orders/", views.OrderListView.as_view(), name="orders"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/status/", views.order_status, name="order_status"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/restock/", views.restock, name="restock"),
    path("ml/", views.ml_insights, name="ml_insights"),
    path("ml/retrain/", views.retrain, name="retrain"),
    path("ml/ab-test/", views.toggle_ab, name="toggle_ab"),
]
