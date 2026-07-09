"""Custom permission decorators for the equipment-reservation app."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_required(view_func):
    """Block access unless the request user is authenticated AND `is_admin`.

    Anonymous users are sent to the login page (via `@login_required`); logged-in
    non-admins get a 403.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_admin:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
