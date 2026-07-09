"""Template helpers for showing live availability in the catalog."""
from datetime import date, timedelta

from django import template
from django.utils import timezone

from reservations.services import available_for

register = template.Library()


@register.filter
def available_on(equipment, iso_date):
    """`{{ equipment|available_on:some_date }}` → integer count of free units.

    `iso_date` may be a `date`, a `datetime`, or an ISO-format string.
    Returns `equipment.total_quantity` when no date is supplied.
    """
    if isinstance(iso_date, str):
        d = date.fromisoformat(iso_date)
    elif hasattr(iso_date, "date"):
        d = iso_date.date()
    else:
        d = iso_date
    if d is None:
        return equipment.total_quantity
    return available_for(equipment, d, d)


@register.simple_tag
def available_in_window(equipment, start, end):
    """`{% available_in_window equipment start end as n %}` — for templates."""
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    return available_for(equipment, start, end)


@register.simple_tag
def default_end_date():
    """Default end date for the reservation form: one week from today."""
    return (timezone.localdate() + timedelta(days=7)).isoformat()


@register.filter
def days_late(reservation):
    """How many days past `end_date` this reservation is. 0 if not overdue."""
    if not reservation.is_overdue:
        return 0
    return (timezone.localdate() - reservation.end_date).days


@register.filter
def get_item(mapping, key):
    """`{{ mydict|get_item:some_key }}` — dict lookup from a template."""
    if mapping is None:
        return None
    return mapping.get(key)
