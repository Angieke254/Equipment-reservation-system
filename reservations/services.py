"""Reservation-related helpers shared by views and the catalog."""
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.urls import reverse

from .models import ACTIVE_STATUSES


def available_for(equipment, start, end, exclude_id=None):
    """How many units of `equipment` are free for the inclusive window [start, end].

    Counts every reservation whose date range overlaps and whose status is
    active (approved or checked_out), then subtracts from `total_quantity`.
    `exclude_id` lets an in-place edit ignore its own row.
    """
    overlapping = equipment.reservations.filter(
        status__in=ACTIVE_STATUSES,
        start_date__lte=end,
        end_date__gte=start,
    )
    if exclude_id is not None:
        overlapping = overlapping.exclude(pk=exclude_id)

    reserved = sum(r.quantity for r in overlapping)
    return max(equipment.total_quantity - reserved, 0)


def has_conflict(equipment, start, end, quantity, exclude_id=None):
    """True if adding a reservation for `quantity` units in [start, end]
    would over-book the equipment. Used as a race-condition guard at approval
    time as well as at request time.
    """
    return quantity > available_for(equipment, start, end, exclude_id=exclude_id)


# Status-specific copy for the borrower notification email. Kept here (not in
# models) so the wording lives next to the rest of the reservation helpers.
_STATUS_MESSAGES = {
    "approved": (
        "Your reservation request has been approved.",
        "You can pick up the equipment at the agreed time.",
    ),
    "rejected": (
        "Your reservation request has been rejected.",
        "Please contact the admin if you have questions.",
    ),
    "checked_out": (
        "Your reservation has been checked out.",
        "Please return the equipment by {end_date}.",
    ),
    "returned": (
        "Your reservation has been marked as returned.",
        "Thanks for returning the equipment on time.",
    ),
}


def notify_status_change(reservation, new_status):
    """Email the borrower when their reservation changes status.

    Called from the admin workflow views. Silently no-ops if the user has
    no email address (e.g. the auto-created superuser with no email set).
    Returns True if a message was sent.
    """
    if new_status not in _STATUS_MESSAGES:
        return False

    user = reservation.user
    if not user.email:
        return False

    subject_prefix, suffix = _STATUS_MESSAGES[new_status]
    subject = f"[Equipment] #{reservation.pk} {subject_prefix}"

    detail_url = reverse("reservation_detail", args=[reservation.pk])
    body = (
        f"Hi {user.username},\n\n"
        f"{suffix}\n\n"
        f"Equipment: {reservation.equipment.name}\n"
        f"Dates: {reservation.start_date} to {reservation.end_date}\n"
        f"Quantity: {reservation.quantity}\n"
        f"Status: {reservation.get_status_display()}\n\n"
        f"View: {detail_url}\n"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=True,
    )
    return True
