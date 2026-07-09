"""URL routes for the accounts app."""
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("history/", views.my_history, name="my_history"),
]
