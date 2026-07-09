"""Forms for the equipment app."""
from django import forms

from .models import Category, Equipment


class EquipmentForm(forms.ModelForm):
    """Create / update an equipment item. Used by admin-only views."""

    class Meta:
        model = Equipment
        fields = (
            "name",
            "category",
            "description",
            "condition",
            "total_quantity",
            "image",
            "image_url",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
