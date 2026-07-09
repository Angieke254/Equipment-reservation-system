"""Forms for accounts: registration and profile editing."""
from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    """Registration form. `is_admin` is intentionally NOT exposed."""

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "department",
            "password1",
            "password2",
        )
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }


class ProfileForm(forms.ModelForm):
    """Editing fields a regular user is allowed to change about themselves."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "department")
        widgets = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
