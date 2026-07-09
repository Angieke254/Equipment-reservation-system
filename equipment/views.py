"""Views for the equipment catalog: list, detail, create, update, delete, history."""
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import admin_required
from .forms import EquipmentForm
from .models import Category, Equipment


def equipment_list(request):
    """Public catalog. Optional `?category=<slug>` and `?q=<text>` filters.

    When no filter is active the page is grouped into one section per category
    with anchor IDs (so the category chips at the top scroll into view).
    When a filter is active we fall back to a single flat grid.
    """
    qs = (
        Equipment.objects.filter(is_active=True)
        .select_related("category")
    )
    category_slug = request.GET.get("category")
    q = request.GET.get("q", "").strip()
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    categories = list(Category.objects.all())

    if q or category_slug:
        # Flat paginated view for filtered results
        paginator = Paginator(qs, 24)
        page_obj = paginator.get_page(request.GET.get("page"))
        sections = [(None, page_obj.object_list)] if page_obj.object_list else []
    else:
        # Grouped view: one section per category, in defined order, skipping
        # categories that have no active items.
        by_cat: dict[int, list] = {c.id: [] for c in categories}
        for item in qs:
            by_cat.setdefault(item.category_id, []).append(item)
        sections = [
            (cat, by_cat[cat.id])
            for cat in categories
            if by_cat[cat.id]
        ]
        page_obj = None

    # Count per category for the chip badges
    cat_counts = {c.id: 0 for c in categories}
    for item in Equipment.objects.filter(is_active=True).only("category_id"):
        cat_counts[item.category_id] = cat_counts.get(item.category_id, 0) + 1

    return render(
        request,
        "equipment/list.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "cat_counts": cat_counts,
            "sections": sections,
            "current_category": category_slug or "",
            "q": q,
        },
    )


def equipment_detail(request, pk):
    """Single item view. Shows the next 30 days of approved/checked-out holds
    so users can see why availability might be limited."""
    equipment = get_object_or_404(
        Equipment.objects.select_related("category"), pk=pk
    )
    today = timezone.localdate()
    horizon = today + timedelta(days=30)

    upcoming = (
        equipment.reservations.filter(
            status__in=["approved", "checked_out"],
            end_date__gte=today,
        )
        .order_by("start_date")
        .select_related("user")
    )
    return render(
        request,
        "equipment/detail.html",
        {
            "equipment": equipment,
            "upcoming": upcoming,
            "today": today,
        },
    )


@admin_required
def equipment_create(request):
    if request.method == "POST":
        form = EquipmentForm(request.POST, request.FILES)
        if form.is_valid():
            equipment = form.save()
            messages.success(request, f"Created {equipment.name}.")
            return redirect("equipment_detail", pk=equipment.pk)
    else:
        form = EquipmentForm()
    return render(
        request,
        "equipment/form.html",
        {"form": form, "title": "Add equipment", "submit_label": "Create"},
    )


@admin_required
def equipment_update(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        form = EquipmentForm(request.POST, request.FILES, instance=equipment)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {equipment.name}.")
            return redirect("equipment_detail", pk=equipment.pk)
    else:
        form = EquipmentForm(instance=equipment)
    return render(
        request,
        "equipment/form.html",
        {
            "form": form,
            "equipment": equipment,
            "title": f"Edit {equipment.name}",
            "submit_label": "Save changes",
        },
    )


@admin_required
def equipment_delete(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        name = equipment.name
        equipment.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("equipment_list")
    return render(
        request,
        "equipment/confirm_delete.html",
        {"equipment": equipment},
    )


@admin_required
def equipment_history(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    reservations = equipment.reservations.select_related("user").order_by("-created_at")
    return render(
        request,
        "equipment/history.html",
        {"equipment": equipment, "reservations": reservations},
    )
