"""URL routes for the REST API."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import EquipmentViewSet, ReservationViewSet

router = DefaultRouter()
router.register(r"equipment", EquipmentViewSet, basename="api-equipment")
router.register(r"reservations", ReservationViewSet, basename="api-reservation")

urlpatterns = [
    path("", include(router.urls)),
]
