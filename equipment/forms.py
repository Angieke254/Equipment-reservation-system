"""Forms for the equipment app."""
from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from .models import Category, Equipment


# Cap uploads at 2 MB. Anything bigger is almost certainly a misuse
# (equipment images are thumbnails, not archival photos).
MAX_IMAGE_UPLOAD_BYTES = 2 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _validate_image(file):
    """Reject empty files, oversize files, and unsupported MIME types."""
    if not isinstance(file, UploadedFile) or not file.name:
        return  # field is optional; no file = no check
    if file.size > MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError(
            f"Image is too large ({file.size // 1024} KB). "
            f"Maximum is {MAX_IMAGE_UPLOAD_BYTES // 1024} KB."
        )
    content_type = (getattr(file, "content_type", "") or "").lower()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported image type '{content_type}'. "
            f"Use JPEG, PNG, or WebP."
        )


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

    def clean_image(self):
        image = self.cleaned_data.get("image")
        _validate_image(image)
        return image
