from django.urls import path

from . import api

app_name = "recommender"

urlpatterns = [
    path("api/recommendations/<int:product_id>/", api.similar, name="similar"),
]
