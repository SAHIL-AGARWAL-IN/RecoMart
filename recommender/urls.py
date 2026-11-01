from django.urls import path

from . import api

app_name = "recommender"

urlpatterns = [
    path("api/recommendations/for-you/", api.for_you, name="for_you"),
    path("api/recommendations/frequently-bought/", api.frequently_bought, name="frequently_bought"),
    path("api/recommendations/<int:product_id>/", api.similar, name="similar"),
]
