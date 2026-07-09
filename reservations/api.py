"""REST API serializers + views for the equipment reservation system.

Mounted at /api/ via `reservations.api_urls`.
Auth: session or HTTP basic. Browsable API is enabled for development.
"""
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from equipment.models import Equipment

from .forms import ReservationRequestForm
from .models import Reservation
from .services import has_conflict


# ---- Serializers -------------------------------------------------------

class EquipmentSerializer(serializers.ModelSerializer):
    """Read-only equipment representation for the catalog API."""
    category_name = serializers.CharField(source="category.name", read_only=True)
    available_now = serializers.IntegerField(read_only=True)

    class Meta:
        model = Equipment
        fields = [
            "id",
            "name",
            "category",
            "category_name",
            "description",
            "condition",
            "total_quantity",
            "available_now",
            "image_url",
            "is_active",
        ]


class ReservationSerializer(serializers.ModelSerializer):
    """Reservation read + write.

    `equipment` is referenced by id on input; `equipment_name` is exposed for
    output. `user` is always set from `request.user` on create — clients
    can't book on behalf of someone else.
    """
    equipment_name = serializers.CharField(source="equipment.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reservation
        fields = [
            "id",
            "user",
            "username",
            "equipment",
            "equipment_name",
            "quantity",
            "start_date",
            "end_date",
            "purpose",
            "status",
            "created_at",
            "decided_at",
            "checked_out_at",
            "returned_at",
            "is_overdue",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "created_at",
            "decided_at",
            "checked_out_at",
            "returned_at",
        ]


# ---- Permissions -------------------------------------------------------

class IsOwnerOrAdminForMutation(permissions.BasePermission):
    """Read: any authenticated user. Write (POST/PUT/DELETE): owner or admin.

    The admin has full control; regular users can only create reservations
    for themselves and can't modify ones they don't own.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return True  # creation is allowed; ownership checked at object level

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id or request.user.is_admin


# ---- ViewSets ----------------------------------------------------------

class EquipmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only catalog endpoint. Filter by category: `?category=<id>`."""
    queryset = Equipment.objects.filter(is_active=True).select_related("category")
    serializer_class = EquipmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        return qs


class ReservationViewSet(viewsets.ModelViewSet):
    """List/create/cancel reservations.

    GET /api/reservations/             — your own reservations (or all if admin)
    POST /api/reservations/            — create a pending reservation
    GET /api/reservations/<id>/        — single reservation
    POST /api/reservations/<id>/cancel/ — cancel your own (or any, if admin)
    """
    serializer_class = ReservationSerializer
    permission_classes = [IsOwnerOrAdminForMutation]

    def get_queryset(self):
        qs = Reservation.objects.select_related("equipment", "user")
        if not self.request.user.is_admin:
            qs = qs.filter(user=self.request.user)
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        # Re-use the same form-level validation as the web view, so
        # the API enforces the borrowing cap and conflict checks too.
        equipment = serializer.validated_data["equipment"]
        form = ReservationRequestForm(
            data={
                "start_date": serializer.validated_data["start_date"],
                "end_date": serializer.validated_data["end_date"],
                "quantity": serializer.validated_data["quantity"],
                "purpose": serializer.validated_data.get("purpose", ""),
            },
            equipment=equipment,
        )
        if not form.is_valid():
            raise serializers.ValidationError(form.errors)

        # Borrowing cap (mirror the web view).
        from django.conf import settings
        active = self.request.user.reservations.filter(
            status__in=["pending", "approved", "checked_out"]
        ).count()
        if active >= settings.MAX_ACTIVE_LOANS:
            raise serializers.ValidationError(
                {"non_field_errors": [
                    f"Active loan limit reached ({settings.MAX_ACTIVE_LOANS})."
                ]}
            )

        # Conflict guard.
        if has_conflict(
            equipment,
            form.cleaned_data["start_date"],
            form.cleaned_data["end_date"],
            form.cleaned_data["quantity"],
        ):
            raise serializers.ValidationError(
                {"non_field_errors": ["Not enough free units in that window."]}
            )

        serializer.save(user=self.request.user, status="pending")

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/reservations/<id>/cancel/ — owner or admin only."""
        reservation = self.get_object()
        if reservation.status not in ("pending", "approved"):
            return Response(
                {"detail": "This reservation can no longer be cancelled."},
                status=400,
            )
        reservation.cancel()
        return Response({"status": "cancelled"})
