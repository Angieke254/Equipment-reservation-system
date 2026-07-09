"""Forms for reservation requests."""
from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Reservation


class ReservationRequestForm(forms.ModelForm):
    """User-facing form to request a reservation against a specific equipment.

    `equipment` is injected from the URL, never user-editable.  The form
    enforces that dates are in the future and that the requested quantity
    fits within the equipment's total stock.
    """

    class Meta:
        model = Reservation
        fields = ("quantity", "start_date", "end_date", "purpose")
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "quantity": forms.NumberInput(attrs={"min": 1}),
            "purpose": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, equipment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.equipment = equipment
        # Sensible defaults: borrow from today for a week
        today = timezone.localdate()
        self.fields["start_date"].initial = today
        self.fields["end_date"].initial = today + timedelta(days=7)
        if equipment:
            self.fields["quantity"].widget.attrs["max"] = equipment.total_quantity
            self.fields["quantity"].help_text = (
                f"Max {equipment.total_quantity} unit(s) for this item."
            )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        qty = cleaned.get("quantity")

        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        if self.equipment and qty and qty > self.equipment.total_quantity:
            self.add_error(
                "quantity",
                f"Only {self.equipment.total_quantity} unit(s) available for this item.",
            )
        return cleaned
