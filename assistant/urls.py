from django.urls import path

from . import api

app_name = "assistant"

urlpatterns = [
    path("api/assistant/", api.reply, name="reply"),
]
