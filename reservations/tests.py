"""Tests for reservation workflow + email notifications."""
from datetime import date, timedelta

from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from equipment.models import Category, Equipment
from reservations.models import Reservation


def _make_world():
    """Standard fixtures: one admin, one borrower (with email), one piece of gear."""
    admin = User.objects.create_user(
        username="admin1", password="pw", is_admin=True, email="admin@x.test"
    )
    borrower = User.objects.create_user(
        username="bob1", password="pw", email="bob@x.test", department="Lab"
    )
    borrower_no_email = User.objects.create_user(
        username="bob2", password="pw", email=""
    )
    category = Category.objects.create(name="Cameras", slug="cameras")
    equipment = Equipment.objects.create(
        name="Canon", category=category, total_quantity=2
    )
    return admin, borrower, borrower_no_email, equipment


def _post(client, url, **extra):
    """Helper: POST with a CSRF token resolved through the test client."""
    csrf = client.get(reverse("login")).cookies
    # Test client bypasses CSRF, but login flow still needs a session user.
    return client.post(url, **extra)


class EmailNotificationTests(TestCase):
    """Each admin workflow action should email the borrower once."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.borrower, cls.no_email, cls.equipment = _make_world()

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)
        self.reservation = Reservation.objects.create(
            user=self.borrower,
            equipment=self.equipment,
            quantity=1,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
            status="pending",
        )

    def _assert_last_email_to(self, user, status_word):
        self.assertEqual(len(mail.outbox), 1, "expected exactly one email")
        msg = mail.outbox[0]
        self.assertIn(user.email, msg.recipients())
        self.assertIn(f"#{self.reservation.pk}", msg.subject)
        self.assertIn(status_word, msg.body.lower())

    def test_approve_sends_email(self):
        self.client.post(reverse("approve_reservation", args=[self.reservation.pk]))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, "approved")
        self._assert_last_email_to(self.borrower, "approved")

    def test_reject_sends_email(self):
        self.client.post(
            reverse("reject_reservation", args=[self.reservation.pk]),
            {"notes": "Out of stock"},
        )
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, "rejected")
        self._assert_last_email_to(self.borrower, "rejected")

    def test_checkout_sends_email(self):
        self.reservation.approve(self.admin)
        mail.outbox = []  # clear the approval email
        self.client.post(reverse("checkout_reservation", args=[self.reservation.pk]))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, "checked_out")
        self._assert_last_email_to(self.borrower, "checked out")

    def test_return_sends_email(self):
        self.reservation.approve(self.admin)
        self.reservation.check_out()
        mail.outbox = []
        self.client.post(reverse("mark_returned", args=[self.reservation.pk]))
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, "returned")
        self._assert_last_email_to(self.borrower, "returned")

    def test_no_email_when_borrower_has_no_email(self):
        """Borrower with empty email field: still flip status, but no message sent."""
        r = Reservation.objects.create(
            user=self.no_email,
            equipment=self.equipment,
            quantity=1,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
            status="pending",
        )
        self.client.post(reverse("approve_reservation", args=[r.pk]))
        r.refresh_from_db()
        self.assertEqual(r.status, "approved")
        self.assertEqual(len(mail.outbox), 0)


class NotifyHelperTests(TestCase):
    """The notify_status_change() helper itself, exercised directly."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.borrower, cls.no_email, cls.equipment = _make_world()

    def setUp(self):
        self.reservation = Reservation.objects.create(
            user=self.borrower,
            equipment=self.equipment,
            quantity=1,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status="pending",
        )

    def test_unknown_status_is_noop(self):
        from reservations.services import notify_status_change
        result = notify_status_change(self.reservation, "weird_status")
        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)


class OverdueTests(TestCase):
    """`is_overdue` and the mark_overdue management command."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.borrower, cls.no_email, cls.equipment = _make_world()
        cls.today = date.today()

    def _make(self, status, end_date):
        return Reservation.objects.create(
            user=self.borrower,
            equipment=self.equipment,
            quantity=1,
            start_date=self.today - timedelta(days=10),
            end_date=end_date,
            status=status,
        )

    def test_overdue_when_checked_out_past_end(self):
        r = self._make("checked_out", self.today - timedelta(days=2))
        self.assertTrue(r.is_overdue)

    def test_not_overdue_when_checked_out_future(self):
        r = self._make("checked_out", self.today + timedelta(days=1))
        self.assertFalse(r.is_overdue)

    def test_not_overdue_when_approved_past_end(self):
        r = self._make("approved", self.today - timedelta(days=2))
        self.assertFalse(r.is_overdue)

    def test_not_overdue_when_returned_past_end(self):
        r = self._make("returned", self.today - timedelta(days=2))
        self.assertFalse(r.is_overdue)

    def test_not_overdue_when_pending_past_end(self):
        r = self._make("pending", self.today - timedelta(days=2))
        self.assertFalse(r.is_overdue)

    def test_mark_overdue_command_lists_overdue(self):
        from django.core.management import call_command
        from io import StringIO

        overdue = self._make("checked_out", self.today - timedelta(days=3))
        self._make("checked_out", self.today + timedelta(days=1))  # not overdue
        self._make("returned", self.today - timedelta(days=3))      # not overdue

        out = StringIO()
        call_command("mark_overdue", stdout=out)
        output = out.getvalue()
        self.assertIn(str(overdue.pk), output)
        self.assertIn("overdue", output.lower())

    def test_mark_overdue_command_no_results(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("mark_overdue", stdout=out)
        self.assertIn("No overdue", out.getvalue())


class CalendarViewTests(TestCase):
    """The /reservations/calendar/ view (admin only)."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.borrower, _, cls.equipment = _make_world()
        cls.other_equipment = Equipment.objects.create(
            name="Other", category=cls.equipment.category, total_quantity=1
        )
        cls.today = date.today()
        cls.reservation = Reservation.objects.create(
            user=cls.borrower,
            equipment=cls.equipment,
            quantity=1,
            start_date=cls.today,
            end_date=cls.today + timedelta(days=2),
            status="approved",
        )

    def setUp(self):
        self.client = Client()

    def test_calendar_requires_admin(self):
        self.client.force_login(self.borrower)
        resp = self.client.get(reverse("reservation_calendar"))
        self.assertEqual(resp.status_code, 403)

    def test_calendar_renders_for_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("reservation_calendar"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.equipment.name)
        self.assertContains(resp, "Reservation calendar")

    def test_calendar_filters_by_equipment(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("reservation_calendar"),
            {"equipment": self.other_equipment.pk},
        )
        self.assertEqual(resp.status_code, 200)
        # The reservation is for `equipment` (Canon), not `other_equipment`.
        # When filtering to other, the Canon's event card should not appear.
        # The legend at the bottom of the page reuses the class names, so we
        # check for the username that appears on the event card instead.
        self.assertNotContains(resp, "bob1")

    def test_calendar_excludes_terminal_reservations(self):
        # A returned reservation should not show up in the calendar.
        returned = Reservation.objects.create(
            user=self.borrower,
            equipment=self.equipment,
            quantity=1,
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            status="returned",
        )
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("reservation_calendar"),
            {"equipment": self.equipment.pk, "month": self.today.strftime("%Y-%m")},
        )
        # Only the approved reservation (not the returned one) should appear.
        # Each event card links to /reservations/<pk>/. Count unique pk values.
        import re
        pks = set(re.findall(
            rb'href="/reservations/(\d+)/"', resp.content
        ))
        self.assertEqual(pks, {str(self.reservation.pk).encode()})
        self.assertNotIn(str(returned.pk).encode(), pks)

    def test_calendar_navigates_to_specific_month(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("reservation_calendar"), {"month": "2030-03"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "March 2030")


class BorrowingLimitTests(TestCase):
    """Per-user MAX_ACTIVE_LOANS cap."""

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.borrower, _, cls.equipment = _make_world()
        cls.post_data = {
            "start_date": (date.today() + timedelta(days=1)).isoformat(),
            "end_date": (date.today() + timedelta(days=3)).isoformat(),
            "quantity": 1,
            "purpose": "Test",
        }
        cls.url = None  # set in setUp once equipment.pk is known

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.borrower)
        self.url = reverse("request_reservation", args=[self.equipment.pk])

    def _post(self):
        return self.client.post(self.url, self.post_data)

    def _make_active(self, status):
        return Reservation.objects.create(
            user=self.borrower,
            equipment=self.equipment,
            quantity=1,
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=6),
            status=status,
        )

    def test_below_limit_allowed(self):
        self._make_active("pending")
        resp = self._post()
        # New pending request was saved → redirect to my_reservations
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.borrower.reservations.filter(status="pending").count(), 2)

    def test_at_limit_blocked(self):
        for s in ("pending", "approved", "checked_out"):
            self._make_active(s)
        resp = self._post()
        # Rendered the form with an error, not a redirect.
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "limit")
        self.assertEqual(self.borrower.reservations.count(), 3)

    def test_terminal_reservations_dont_count(self):
        # 5 returned + 2 rejected + 1 cancelled = none of these count.
        for _ in range(5):
            self._make_active("returned")
        for _ in range(2):
            self._make_active("rejected")
        self._make_active("cancelled")
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        # 1 new pending was created; nothing else was pending before.
        self.assertEqual(
            self.borrower.reservations.filter(status="pending").count(), 1
        )

    def test_per_user_isolation(self):
        # Other users' active loans don't count against this user.
        other = User.objects.create_user(username="other", password="pw")
        for s in ("pending", "approved", "checked_out"):
            Reservation.objects.create(
                user=other,
                equipment=self.equipment,
                quantity=1,
                start_date=date.today() + timedelta(days=10),
                end_date=date.today() + timedelta(days=11),
                status=s,
            )
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
