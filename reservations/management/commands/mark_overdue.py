"""`manage.py mark_overdue` — report reservations that are checked out past their end date.

This does NOT change any rows. Overdue status is computed from `is_overdue`
on the Reservation model, so it stays correct without a write. The command
exists so an admin (or cron) can see the current overdue list and act on it.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from reservations.models import Reservation


class Command(BaseCommand):
    help = "List reservations that are checked out past their end date."

    def handle(self, *args, **options):
        today = timezone.localdate()
        overdue = [
            r for r in Reservation.objects.select_related("user", "equipment")
            if r.is_overdue
        ]
        if not overdue:
            self.stdout.write(self.style.SUCCESS(f"No overdue reservations as of {today}."))
            return

        self.stdout.write(self.style.WARNING(f"{len(overdue)} overdue reservation(s):"))
        for r in overdue:
            days_late = (today - r.end_date).days
            self.stdout.write(
                f"  #{r.pk}  {r.user.username:<12}  {r.equipment.name:<20}  "
                f"end={r.end_date}  ({days_late} day(s) late)"
            )
