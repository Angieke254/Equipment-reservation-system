from django.contrib import admin

from .models import Category, Equipment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "condition", "total_quantity", "is_active")
    list_filter = ("category", "condition", "is_active")
    search_fields = ("name", "description")
    autocomplete_fields = ("category",)
