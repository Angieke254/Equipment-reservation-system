"""Catalog models: categories of equipment and individual equipment items."""
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("equipment_list") + f"?category={self.slug}"


CONDITION_CHOICES = [
    ("excellent", "Excellent"),
    ("good", "Good"),
    ("fair", "Fair"),
    ("needs_repair", "Needs repair"),
]


class Equipment(models.Model):
    name = models.CharField(max_length=120)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="equipment"
    )
    description = models.TextField(blank=True)
    condition = models.CharField(
        max_length=20, choices=CONDITION_CHOICES, default="good"
    )
    total_quantity = models.PositiveIntegerField(
        default=1,
        help_text="How many physical units of this item the organization owns.",
    )
    image_url = models.URLField(
        blank=True,
        help_text="Remote image URL (used if no file is uploaded).",
    )
    image = models.ImageField(
        upload_to="equipment/",
        blank=True,
        null=True,
        help_text="Local image upload. Takes precedence over image_url.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive items are hidden from the catalog but kept for history.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("equipment_detail", args=[self.pk])

    def available_now(self):
        """How many units are free for an unspecified window starting today."""
        from django.utils import timezone
        from reservations.services import available_for

        today = timezone.localdate()
        return available_for(self, today, today)

    @property
    def display_image_url(self):
        """The image to show in templates: uploaded file first, then URL."""
        try:
            if self.image:
                return self.image.url
        except (ValueError, AttributeError):
            pass
        return self.image_url or ""
