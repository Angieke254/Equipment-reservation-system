"""URL routes for the reservations app."""
from django.urls import path

from . import views

urlpatterns = [
    path("", views.my_reservations, name="my_reservations"),
    path("manage/", views.manage_queue, name="manage_queue"),
    path("calendar/", views.calendar_view, name="reservation_calendar"),
    path("request/<int:pk>/", views.request_reservation, name="request_reservation"),
    path("<int:pk>/", views.reservation_detail, name="reservation_detail"),
    path("<int:pk>/cancel/", views.cancel_reservation, name="cancel_reservation"),
    path("<int:pk>/approve/", views.approve_reservation, name="approve_reservation"),
    path("<int:pk>/reject/", views.reject_reservation, name="reject_reservation"),
    path("<int:pk>/checkout/", views.checkout_reservation, name="checkout_reservation"),
    path(
        "<int:pk>/mark-returned/",
        views.mark_returned,
        name="mark_returned",
    ),
]
