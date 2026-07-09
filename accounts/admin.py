from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class UserAdminConfig(UserAdmin):
    """Standard UserAdmin plus our two extra fields on the edit form."""
    fieldsets = UserAdmin.fieldsets + (
        ("Equipment Reservation", {"fields": ("is_admin", "department")}),
    )
    list_display = ("username", "email", "is_admin", "is_staff", "department")
    list_filter = UserAdmin.list_filter + ("is_admin",)
    search_fields = ("username", "email", "first_name", "last_name", "department")
