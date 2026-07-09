"""Views for the reservation workflow: request, view, cancel, approve, check out, return."""
import calendar as _cal
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import admin_required
from equipment.models import Equipment
from .forms import ReservationRequestForm
from .models import Reservation
from .services import available_for, has_conflict, notify_status_change


# ---- User-facing --------------------------------------------------------

@login_required
def request_reservation(request, pk):
    """Create a new pending reservation for a piece of equipment."""
    from django.conf import settings

    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        form = ReservationRequestForm(request.POST, equipment=equipment)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.equipment = equipment
            reservation.user = request.user
            reservation.status = "pending"

            # Per-user borrowing cap. Counts everything that ties up gear:
            # pending (waiting), approved (reserved), checked_out (in hand).
            active_count = request.user.reservations.filter(
                status__in=["pending", "approved", "checked_out"]
            ).count()
            if active_count >= settings.MAX_ACTIVE_LOANS:
                form.add_error(
                    None,
                    f"You already have {active_count} active reservation(s). "
                    f"The limit is {settings.MAX_ACTIVE_LOANS}. "
                    f"Return or cancel one before requesting another.",
                )
            # Re-check conflict with the form's cleaned values (race guard)
            elif has_conflict(
                equipment,
                reservation.start_date,
                reservation.end_date,
                reservation.quantity,
            ):
                form.add_error(
                    None,
                    f"Not enough free units in the requested window "
                    f"({available_for(equipment, reservation.start_date, reservation.end_date)} of "
                    f"{equipment.total_quantity} free).",
                )
            else:
                reservation.save()
                messages.success(
                    request,
                    f"Reservation request submitted for {equipment.name}.",
                )
                return redirect("my_reservations")
    else:
        form = ReservationRequestForm(equipment=equipment)
    return render(
        request,
        "reservations/request.html",
        {"form": form, "equipment": equipment},
    )


@login_required
def my_reservations(request):
    """List the current user's reservations, grouped by lifecycle phase."""
    qs = request.user.reservations.select_related(
        "equipment", "equipment__category"
    )
    pending = [r for r in qs if r.status == "pending"]
    active = [r for r in qs if r.status in ("approved", "checked_out")]
    past = [r for r in qs if r.status in ("returned", "rejected", "cancelled")]
    return render(
        request,
        "reservations/my_reservations.html",
        {
            "pending": pending,
            "active": active,
            "past": past,
        },
    )


@login_required
def reservation_detail(request, pk):
    reservation = get_object_or_404(
        Reservation.objects.select_related("equipment", "user", "decided_by"),
        pk=pk,
    )
    is_owner = reservation.user_id == request.user.id
    if not (is_owner or request.user.is_admin):
        raise PermissionDenied
    return render(
        request,
        "reservations/detail.html",
        {
            "reservation": reservation,
            "is_owner": is_owner,
            "can_cancel": is_owner and reservation.status in ("pending", "approved"),
        },
    )


@login_required
def cancel_reservation(request, pk):
    """Owner-initiated cancellation. Only allowed while still pending/approved."""
    reservation = get_object_or_404(Reservation, pk=pk, user=request.user)
    if request.method != "POST":
        return redirect("reservation_detail", pk=pk)
    if reservation.status not in ("pending", "approved"):
        messages.warning(request, "This reservation can no longer be cancelled.")
        return redirect("reservation_detail", pk=pk)
    reservation.cancel()
    messages.success(request, "Reservation cancelled.")
    return redirect("my_reservations")


# ---- Admin workflow -----------------------------------------------------

@admin_required
def manage_queue(request):
    """Admin: list of pending requests, oldest first, grouped by user."""
    pending = (
        Reservation.objects.filter(status="pending")
        .select_related("user", "equipment", "equipment__category")
        .order_by("created_at")
    )
    overdue_qs = (
        Reservation.objects.filter(status="checked_out")
        .select_related("user", "equipment", "equipment__category")
    )
    overdue = [r for r in overdue_qs if r.is_overdue]
    return render(
        request,
        "reservations/manage.html",
        {"pending": pending, "overdue": overdue},
    )


@admin_required
@transaction.atomic
def approve_reservation(request, pk):
    if request.method != "POST":
        return redirect("reservation_detail", pk=pk)
    reservation = get_object_or_404(
        Reservation.objects.select_for_update(), pk=pk
    )
    if reservation.status != "pending":
        messages.warning(request, "Only pending requests can be approved.")
        return redirect("reservation_detail", pk=pk)
    # Race-condition guard: re-check at approval time
    if has_conflict(
        reservation.equipment,
        reservation.start_date,
        reservation.end_date,
        reservation.quantity,
        exclude_id=reservation.pk,
    ):
        free = available_for(
            reservation.equipment,
            reservation.start_date,
            reservation.end_date,
        )
        messages.error(
            request,
            f"Cannot approve #{reservation.pk}: only {free} unit(s) free in the requested window.",
        )
        return redirect("reservation_detail", pk=pk)
    reservation.approve(request.user)
    notify_status_change(reservation, "approved")
    messages.success(
        request, f"Approved reservation #{reservation.pk} for {reservation.user.username}."
    )
    return redirect("reservation_detail", pk=pk)


@admin_required
@transaction.atomic
def reject_reservation(request, pk):
    if request.method != "POST":
        return redirect("reservation_detail", pk=pk)
    reservation = get_object_or_404(
        Reservation.objects.select_for_update(), pk=pk
    )
    if reservation.status != "pending":
        messages.warning(request, "Only pending requests can be rejected.")
        return redirect("reservation_detail", pk=pk)
    notes = request.POST.get("notes", "")
    reservation.reject(request.user, notes=notes)
    notify_status_change(reservation, "rejected")
    messages.success(
        request, f"Rejected reservation #{reservation.pk}."
    )
    return redirect("reservation_detail", pk=pk)


@admin_required
@transaction.atomic
def checkout_reservation(request, pk):
    if request.method != "POST":
        return redirect("reservation_detail", pk=pk)
    reservation = get_object_or_404(
        Reservation.objects.select_for_update(), pk=pk
    )
    if reservation.status != "approved":
        messages.warning(request, "Only approved reservations can be checked out.")
        return redirect("reservation_detail", pk=pk)
    reservation.check_out()
    notify_status_change(reservation, "checked_out")
    messages.success(
        request, f"Checked out #{reservation.pk} to {reservation.user.username}."
    )
    return redirect("reservation_detail", pk=pk)


@admin_required
@transaction.atomic
def mark_returned(request, pk):
    if request.method != "POST":
        return redirect("reservation_detail", pk=pk)
    reservation = get_object_or_404(
        Reservation.objects.select_for_update(), pk=pk
    )
    if reservation.status != "checked_out":
        messages.warning(request, "Only checked-out reservations can be returned.")
        return redirect("reservation_detail", pk=pk)
    reservation.mark_returned()
    notify_status_change(reservation, "returned")
    messages.success(request, f"Marked #{reservation.pk} as returned.")
    return redirect("reservation_detail", pk=pk)


# ---- Calendar ---------------------------------------------------------

@admin_required
def calendar_view(request):
    """Month-grid view of who has what when.

    `?month=YYYY-MM` chooses the month (default: current month).
    `?equipment=<id>` filters to a single piece of equipment.
    Cells are colored by status (approved/checked_out/pending).
    """
    from equipment.models import Equipment  # local import: avoid circular

    # 1. Parse month.
    month_str = request.GET.get("month")
    today = date.today()
    if month_str:
        try:
            year, month = (int(x) for x in month_str.split("-"))
        except (ValueError, AttributeError):
            year, month = today.year, today.month
    else:
        year, month = today.year, today.month

    # 2. Build the grid: list of weeks, each a list of 7 (date|None) tuples.
    cal = _cal.Calendar(firstweekday=0)  # Monday-first like a workweek
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        weeks.append([date(year, month, d) if d else None for d in week])

    # 3. Range covered by the grid (including leading/trailing days from siblings).
    flat_days = [d for w in weeks for d in w if d]
    range_start, range_end = flat_days[0], flat_days[-1]

    # 4. Filter equipment.
    equipment_id = request.GET.get("equipment")
    all_equipment = Equipment.objects.filter(is_active=True).order_by("name")
    if equipment_id:
        try:
            equipment_filter = Equipment.objects.get(pk=int(equipment_id))
        except (ValueError, Equipment.DoesNotExist):
            equipment_filter = None
    else:
        equipment_filter = None

    # 5. Pull reservations overlapping the visible range. We exclude terminal
    #    statuses (rejected/cancelled/returned) — the calendar shows "what's
    #    actually holding equipment out", not historical noise.
    qs = (
        Reservation.objects
        .filter(start_date__lte=range_end, end_date__gte=range_start)
        .exclude(status__in=["rejected", "cancelled", "returned"])
        .select_related("user", "equipment")
    )
    if equipment_filter:
        qs = qs.filter(equipment=equipment_filter)

    # 6. Bucket by date → list of reservations active that day.
    by_day = {d: [] for d in flat_days}
    for r in qs:
        d = max(r.start_date, range_start)
        end = min(r.end_date, range_end)
        while d <= end:
            by_day.setdefault(d, []).append(r)
            d += timedelta(days=1)

    # 7. Navigation links: previous / next month.
    if month == 1:
        prev_month = f"{year - 1}-12"
        next_month = f"{year}-02"
    elif month == 12:
        prev_month = f"{year}-11"
        next_month = f"{year + 1}-01"
    else:
        prev_month = f"{year}-{month - 1:02d}"
        next_month = f"{year}-{month + 1:02d}"

    return render(
        request,
        "reservations/calendar.html",
        {
            "weeks": weeks,
            "by_day": by_day,
            "today": today,
            "month_label": date(year, month, 1).strftime("%B %Y"),
            "all_equipment": all_equipment,
            "equipment_filter": equipment_filter,
            "prev_month": prev_month,
            "next_month": next_month,
            "current_month": f"{year}-{month:02d}",
        },
    )
