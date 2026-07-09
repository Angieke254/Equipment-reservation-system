"""Tests for the REST API at /api/."""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from equipment.models import Category, Equipment
from reservations.models import Reservation


def _make_world():
    admin = User.objects.create_user(
        username="admin1", password="pw", is_admin=True
    )
    borrower = User.objects.create_user(username="bob", password="pw")
    other = User.objects.create_user(username="carol", password="pw")
    category = Category.objects.create(name="C", slug="c")
    eq = Equipment.objects.create(name="Canon", category=category, total_quantity=1)
    return admin, borrower, other, eq


class EquipmentAPITests(TestCase):
    def setUp(self):
        self.admin, self.borrower, _, self.equipment = _make_world()
        self.client = APIClient()
        self.client.force_authenticate(self.borrower)

    def test_list_equipment(self):
        resp = self.client.get("/api/equipment/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        names = [e["name"] for e in results]
        self.assertIn("Canon", names)

    def test_unauthenticated_blocked(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/equipment/")
        self.assertEqual(resp.status_code, 403)

    def test_filter_by_category(self):
        cat2 = Category.objects.create(name="D", slug="d")
        Equipment.objects.create(name="Other", category=cat2, total_quantity=1)
        resp = self.client.get(f"/api/equipment/?category={self.equipment.category_id}")
        results = resp.json()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Canon")


class ReservationAPITests(TestCase):
    def setUp(self):
        self.admin, self.borrower, self.other, self.equipment = _make_world()
        self.client = APIClient()
        self.client.force_authenticate(self.borrower)
        self.payload = {
            "equipment": self.equipment.pk,
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "quantity": 1,
            "purpose": "Test",
        }

    def test_list_only_own(self):
        Reservation.objects.create(
            user=self.other, equipment=self.equipment, quantity=1,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            status="pending",
        )
        resp = self.client.get("/api/reservations/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        for r in results:
            self.assertEqual(r["username"], "bob")

    def test_admin_sees_all(self):
        Reservation.objects.create(
            user=self.borrower, equipment=self.equipment, quantity=1,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            status="pending",
        )
        Reservation.objects.create(
            user=self.other, equipment=self.equipment, quantity=1,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            status="pending",
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/reservations/")
        self.assertEqual(len(resp.json()), 2)

    def test_create_pending(self):
        resp = self.client.post("/api/reservations/", self.payload, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        r = Reservation.objects.get(pk=resp.json()["id"])
        self.assertEqual(r.user, self.borrower)
        self.assertEqual(r.status, "pending")

    def test_create_conflict_blocked(self):
        # Pre-existing approved reservation uses the only unit.
        Reservation.objects.create(
            user=self.other, equipment=self.equipment, quantity=1,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
            status="approved",
        )
        resp = self.client.post("/api/reservations/", self.payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_create_respects_borrowing_limit(self):
        # Borrow already at the cap.
        for i in range(3):
            Reservation.objects.create(
                user=self.borrower, equipment=self.equipment, quantity=1,
                start_date=date.today() + timedelta(days=10 + i),
                end_date=date.today() + timedelta(days=11 + i),
                status="pending",
            )
        resp = self.client.post("/api/reservations/", self.payload, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_cancel(self):
        r = Reservation.objects.create(
            user=self.borrower, equipment=self.equipment, quantity=1,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            status="pending",
        )
        resp = self.client.post(f"/api/reservations/{r.pk}/cancel/")
        self.assertEqual(resp.status_code, 200)
        r.refresh_from_db()
        self.assertEqual(r.status, "cancelled")

    def test_cannot_cancel_others(self):
        r = Reservation.objects.create(
            user=self.other, equipment=self.equipment, quantity=1,
            start_date=date.today(), end_date=date.today() + timedelta(days=1),
            status="pending",
        )
        resp = self.client.post(f"/api/reservations/{r.pk}/cancel/")
        # Read is OK, but the cancel action requires object-level permission.
        # On detail endpoints the framework returns 403 when has_object_permission fails.
        self.assertIn(resp.status_code, (403, 404))
