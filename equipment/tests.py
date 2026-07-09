"""Tests for the image upload feature on Equipment."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from equipment.models import Category, Equipment


def _make_png_bytes():
    """Generate a tiny valid PNG in memory."""
    img = Image.new("RGB", (8, 8), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_world():
    admin = User.objects.create_user(
        username="admin1", password="pw", is_admin=True
    )
    cat = Category.objects.create(name="C", slug="c")
    return admin, cat


class ImageUploadTests(TestCase):
    def setUp(self):
        self.admin, self.cat = _make_world()
        self.client = Client()
        self.client.force_login(self.admin)

    def test_upload_image_saves_to_equipment(self):
        png = _make_png_bytes()
        uploaded = SimpleUploadedFile(
            "test.png", png, content_type="image/png"
        )
        resp = self.client.post(
            reverse("equipment_create"),
            {
                "name": "Canon",
                "category": self.cat.pk,
                "condition": "good",
                "total_quantity": 1,
                "image": uploaded,
            },
        )
        # Successful create redirects to detail
        self.assertEqual(resp.status_code, 302)
        eq = Equipment.objects.get(name="Canon")
        self.assertTrue(bool(eq.image), "image should be set on the model")
        # File is served from MEDIA_ROOT/equipment/<file>
        self.assertIn("equipment/", eq.image.name)

    def test_display_image_url_prefers_uploaded(self):
        """uploaded file wins over image_url."""
        eq = Equipment.objects.create(
            name="X", category=self.cat, total_quantity=1,
            image_url="https://example.com/x.png",
        )
        png = _make_png_bytes()
        eq.image.save("uploaded.png", io.BytesIO(png), save=True)
        # Django may rename the file (collision avoidance), but the basename
        # of the original is preserved.
        self.assertIn("uploaded", eq.display_image_url)
        self.assertNotIn("example.com", eq.display_image_url)

    def test_display_image_url_falls_back_to_image_url(self):
        """No upload → image_url is used."""
        eq = Equipment.objects.create(
            name="X", category=self.cat, total_quantity=1,
            image_url="https://example.com/x.png",
        )
        self.assertEqual(eq.display_image_url, "https://example.com/x.png")

    def test_display_image_url_empty(self):
        """Neither → empty string."""
        eq = Equipment.objects.create(
            name="X", category=self.cat, total_quantity=1,
        )
        self.assertEqual(eq.display_image_url, "")

    def test_update_can_replace_image(self):
        eq = Equipment.objects.create(
            name="X", category=self.cat, total_quantity=1, condition="good",
        )
        png = _make_png_bytes()
        resp = self.client.post(
            reverse("equipment_update", args=[eq.pk]),
            {
                "name": "X renamed",
                "category": self.cat.pk,
                "condition": "good",
                "total_quantity": 1,
                "image": SimpleUploadedFile("new.png", png, content_type="image/png"),
            },
        )
        self.assertEqual(resp.status_code, 302)
        eq.refresh_from_db()
        self.assertEqual(eq.name, "X renamed")
        self.assertTrue(bool(eq.image))
