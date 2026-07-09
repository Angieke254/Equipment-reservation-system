"""Reservation model — a user's request to borrow equipment over a date range."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("checked_out", "Checked out"),
    ("returned", "Returned"),
    ("cancelled", "Cancelled"),
]

# Statuses that hold equipment out of the pool of available units.
ACTIVE_STATUSES = ["approved", "checked_out"]


class Reservation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    equipment = models.ForeignKey(
        "equipment.Equipment",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    quantity = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField()
    purpose = models.TextField(blank=True)

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_reservations",
    )
    checked_out_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(
        blank=True,
        help_text="Optional reason from the admin (rejection, etc.).",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["equipment", "status", "start_date", "end_date"]
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="reservation_dates_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="reservation_quantity_at_least_one",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} → {self.equipment.name} "
            f"({self.start_date}–{self.end_date})"
        )

    def get_absolute_url(self):
        return reverse("reservation_detail", args=[self.pk])

    # ---- Validation -----------------------------------------------------

    def clean(self):
        """Model-level validation. Always call `full_clean()` in forms before save."""
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        if self.equipment_id and self.quantity and self.quantity > self.equipment.total_quantity:
            raise ValidationError(
                {"quantity": f"Only {self.equipment.total_quantity} unit(s) available."}
            )

    # ---- Status helpers -------------------------------------------------

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def is_pending(self):
        return self.status == "pending"

    @property
    def is_terminal(self):
        return self.status in ("returned", "rejected", "cancelled")

    @property
    def is_overdue(self):
        """True when checked out past the agreed end date and not yet returned.

        Computed from status + end_date so it never goes stale without a write.
        `approved` reservations whose end date has passed are NOT considered
        overdue here — they just need to be picked up. Once they transition
        to `checked_out` and the clock runs out, this flips on.
        """
        if self.status != "checked_out":
            return False
        return self.end_date < timezone.localdate()

    def approve(self, by_user):
        self.status = "approved"
        self.decided_at = timezone.now()
        self.decided_by = by_user
        self.save(update_fields=["status", "decided_at", "decided_by"])

    def reject(self, by_user, notes=""):
        self.status = "rejected"
        self.decided_at = timezone.now()
        self.decided_by = by_user
        self.decision_notes = notes
        self.save(update_fields=["status", "decided_at", "decided_by", "decision_notes"])

    def cancel(self):
        self.status = "cancelled"
        self.save(update_fields=["status"])

    def check_out(self):
        if self.status != "approved":
            raise ValidationError("Only approved reservations can be checked out.")
        self.status = "checked_out"
        self.checked_out_at = timezone.now()
        self.save(update_fields=["status", "checked_out_at"])

    def mark_returned(self):
        if self.status != "checked_out":
            raise ValidationError("Only checked-out reservations can be returned.")
        self.status = "returned"
        self.returned_at = timezone.now()
        self.save(update_fields=["status", "returned_at"])
