import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.catalog.models import Category, Product


def _cp1251_extended_chars():
    chars = []
    for value in range(0x80, 0xC0):
        try:
            chars.append(bytes([value]).decode("cp1251"))
        except UnicodeDecodeError:
            continue
    return "".join(chars)


_MOJIBAKE_PREFIX = "".join(chr(codepoint) for codepoint in (0x420, 0x421))
# A single pair can occur in valid Ukrainian words such as "Рівно".
_MOJIBAKE_PATTERN = re.compile(
    rf"(?:[{re.escape(_MOJIBAKE_PREFIX)}][{re.escape(_cp1251_extended_chars())}]){{2,}}"
)


class SourceEncodingGuardTests(SimpleTestCase):
    SOURCE_GLOBS = (
        "templates/**/*.html",
        "apps/**/templates/**/*.html",
        "apps/**/*.py",
        "static/**/*.js",
        "static/**/*.css",
    )
    SKIP_DIRS = {"migrations", "__pycache__", ".venv", ".git"}

    def test_mojibake_pattern_accepts_ukrainian_text(self):
        for text in ("Рівно 3 цифри.", "Різні товари", "Сірий смартфон", "з батареєю 87%."):
            with self.subTest(text=text):
                self.assertIsNone(_MOJIBAKE_PATTERN.search(text))

    def test_mojibake_pattern_detects_misdecoded_utf8(self):
        for text in ("каталог", "батареєю", "Смартфон у хорошому стані."):
            with self.subTest(text=text):
                corrupted = text.encode("utf-8").decode("cp1251")
                self.assertIsNotNone(_MOJIBAKE_PATTERN.search(corrupted))

    def _iter_source_paths(self):
        base_dir = Path(settings.BASE_DIR)
        paths = set()
        for pattern in self.SOURCE_GLOBS:
            for path in base_dir.glob(pattern):
                if not path.is_file():
                    continue
                if any(part in self.SKIP_DIRS for part in path.parts):
                    continue
                paths.add(path)
        return sorted(paths)

    def test_text_sources_are_valid_utf8(self):
        invalid_files = []

        for path in self._iter_source_paths():
            try:
                path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                invalid_files.append(f"{path.relative_to(settings.BASE_DIR)} ({exc})")

        self.assertEqual(
            invalid_files,
            [],
            "Files must be UTF-8 encoded:\n" + "\n".join(invalid_files),
        )

    def test_text_sources_do_not_contain_mojibake_signatures(self):
        suspicious_lines = []
        base_dir = Path(settings.BASE_DIR)

        for path in self._iter_source_paths():
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if _MOJIBAKE_PATTERN.search(line):
                    suspicious_lines.append(f"{path.relative_to(base_dir)}:{line_number}")
                    if len(suspicious_lines) >= 30:
                        break
            if len(suspicious_lines) >= 30:
                break

        self.assertEqual(
            suspicious_lines,
            [],
            "Potential mojibake found:\n" + "\n".join(suspicious_lines),
        )


class PageEncodingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()
        cls.user = cls.user_model.objects.create_user(
            username="+380501010101",
            phone="+380501010101",
            first_name="Test",
            last_name="User",
            password="QpStrongPass123!",
        )
        cls.category = Category.objects.create(name="Phones", slug="phones")
        cls.product = Product.objects.create(
            category=cls.category,
            title="Test Product",
            brand="Apple",
            model_name="A0001",
            description="Test description",
            condition_score=Decimal("9.0"),
            price_uah=Decimal("10000.00"),
            is_available=True,
            is_active=True,
        )

    def _assert_utf8_response(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, f"Unexpected status for {url}")
        content_type = response.headers.get("Content-Type", "").lower()
        self.assertIn("charset=utf-8", content_type, f"Missing UTF-8 charset on {url}")
        response.content.decode("utf-8")

    def test_public_pages_serve_utf8(self):
        urls = [
            reverse("home"),
            reverse("healthcheck"),
            reverse("catalog:list"),
            reverse("catalog:product_detail", kwargs={"pk": self.product.pk, "slug": "test-product"}),
            reverse("orders:checkout"),
            reverse("orders:cart_badge"),
            reverse("orders:cart_panel"),
            reverse("users:register"),
            reverse("users:login"),
        ]

        for url in urls:
            with self.subTest(url=url):
                self._assert_utf8_response(url)

    def test_profile_page_serves_utf8_for_authenticated_user(self):
        self.client.force_login(self.user)
        self._assert_utf8_response(reverse("users:profile"))
