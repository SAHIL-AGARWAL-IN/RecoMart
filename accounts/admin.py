from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class RecoMartUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    fieldsets = UserAdmin.fieldsets + (("RecoMart", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("RecoMart", {"fields": ("role",)}),)
