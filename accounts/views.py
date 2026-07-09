"""Views for accounts: landing page, registration, profile, history."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from equipment.models import Equipment
from .forms import ProfileForm, RegisterForm


# ---- Auth views (wired in urls.py with as_view) -------------------------

class AppLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class AppLogoutView(LogoutView):
    next_page = reverse_lazy("login")


# ---- Public ------------------------------------------------------------

def home(request):
    """Landing page. Anonymous users see CTAs; logged-in users see the catalog."""
    total_equipment = Equipment.objects.filter(is_active=True).count()
    total_units = sum(
        e.total_quantity for e in Equipment.objects.filter(is_active=True)
    )
    context = {
        "total_equipment": total_equipment,
        "total_units": total_units,
    }
    return render(request, "home.html", context)


def register(request):
    if request.user.is_authenticated:
        return redirect("equipment_list")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account is ready.")
            return redirect("equipment_list")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


# ---- Authenticated -----------------------------------------------------

@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def my_history(request):
    """A single table of every reservation the user has ever made,
    optionally filtered by `?status=pending|approved|...`."""
    qs = request.user.reservations.select_related("equipment", "equipment__category")
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(
        request,
        "accounts/history.html",
        {"reservations": qs, "status_filter": status_filter or ""},
    )
