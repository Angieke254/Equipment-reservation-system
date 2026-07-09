"""Seed the database with an admin, demo users, categories, and sample equipment.

Idempotent: re-running is safe; everything is created with `get_or_create` /
`update_or_create` so existing rows are left alone.

Usage:
    python manage.py seed_data
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from equipment.models import Category, Equipment

User = get_user_model()


SEED_CATEGORIES = [
    {"name": "Cameras",      "slug": "cameras",      "description": "Photo and video cameras, lenses, tripods."},
    {"name": "Projectors",   "slug": "projectors",   "description": "Lecture-hall and meeting-room projectors."},
    {"name": "Lab Devices",  "slug": "lab-devices",  "description": "Microscopes, oscilloscopes, multimeters."},
    {"name": "Laptops",      "slug": "laptops",      "description": "Loaner laptops for staff and students."},
]

SEED_EQUIPMENT = [
    # (name, category_slug, total_qty, condition, description, image_url)
    ("Canon EOS R6",         "cameras",     1, "excellent", "Full-frame mirrorless body, 20MP. Includes battery and 64GB card.",
     "https://images.unsplash.com/photo-1606983340126-99ab4feaa64a?w=600"),
    ("Sony A7 IV",           "cameras",     1, "good",      "33MP full-frame mirrorless. Comes with 28-70mm kit lens.",
     "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=600"),
    ("Epson EB-FH52",        "projectors",  2, "good",      "4000-lumen 1080p projector. HDMI + VGA inputs.",
     "https://images.unsplash.com/photo-1517214451583-b7f0b0e2a39d?w=600"),
    ("Digital Microscope",   "lab-devices", 1, "excellent", "Up to 1000x magnification, USB capture, calibrated reticle.",
     "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=600"),
    ("Oscilloscope",         "lab-devices", 1, "fair",      "100MHz 2-channel bench oscilloscope. Probes included.",
     "https://images.unsplash.com/photo-1581090700227-1e37b190418e?w=600"),
    ("Dell XPS 13",          "laptops",     1, "excellent", "13-inch ultrabook, 16GB RAM, 512GB SSD, Linux preinstalled.",
     "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=600"),
    ("MacBook Pro 14",       "laptops",     1, "good",      "M2 Pro, 16GB RAM, 512GB SSD. For design and video work.",
     "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600"),
]

SEED_USERS = [
    # (username, password, first_name, last_name, email, department, is_admin)
    ("admin", "admin12345", "Admin", "User", "admin@example.com", "Operations", True),
    ("alice", "demo12345",  "Alice", "Park",  "alice@example.com", "Media Lab",   False),
    ("bob",   "demo12345",  "Bob",   "Singh", "bob@example.com",   "Biology",     False),
    ("carol", "demo12345",  "Carol", "Diaz",  "carol@example.com", "IT Support",  False),
]


class Command(BaseCommand):
    help = "Seed the database with an admin, demo users, categories, and equipment."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding users...")
        for username, password, first, last, email, dept, is_admin in SEED_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "department": dept,
                    "is_admin": is_admin,
                    "is_staff": is_admin,
                    "is_superuser": is_admin,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"  + user: {username}"))
            else:
                self.stdout.write(f"  · user already exists: {username}")

        self.stdout.write("Seeding categories...")
        for cat in SEED_CATEGORIES:
            obj, created = Category.objects.get_or_create(slug=cat["slug"], defaults=cat)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + category: {obj.name}"))
            else:
                self.stdout.write(f"  · category already exists: {obj.name}")

        self.stdout.write("Seeding equipment...")
        for name, slug, qty, cond, desc, img in SEED_EQUIPMENT:
            cat = Category.objects.get(slug=slug)
            obj, created = Equipment.objects.get_or_create(
                name=name,
                defaults={
                    "category": cat,
                    "total_quantity": qty,
                    "condition": cond,
                    "description": desc,
                    "image_url": img,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + equipment: {name}"))
            else:
                self.stdout.write(f"  · equipment already exists: {name}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed complete."))
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "  Default credentials:\n"
            "    admin / admin12345   (superuser, is_admin=True)\n"
            "    alice / demo12345\n"
            "    bob   / demo12345\n"
            "    carol / demo12345\n"
            "\n"
            "  >>> Change the admin password before going to production. <<<\n"
        ))
