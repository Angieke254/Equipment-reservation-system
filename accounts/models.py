"""Custom user model with an is_admin flag and a free-text department."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Project user. `is_admin` is the app-level admin role (separate from
    Django's `is_staff` / `is_superuser`, which control /admin/ access)."""

    is_admin = models.BooleanField(
        default=False,
        help_text="Designates whether this user can manage equipment and approve reservations.",
    )
    department = models.CharField(
        max_length=80,
        blank=True,
        help_text="Free-text team or department, e.g. 'Media Lab'.",
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        full = self.get_full_name()
        return f"{self.username} ({full})" if full else self.username
