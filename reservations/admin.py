from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "equipment",
        "start_date",
        "end_date",
        "quantity",
        "status",
        "created_at",
    )
    list_filter = ("status", "equipment__category", "equipment")
    search_fields = ("user__username", "equipment__name", "purpose")
    date_hierarchy = "start_date"
    autocomplete_fields = ("user", "equipment", "decided_by")
    readonly_fields = ("created_at", "decided_at", "checked_out_at", "returned_at")
