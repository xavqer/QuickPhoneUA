from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.catalog.models import Category, DeviceModel, DeviceModelSpec, Product, ProductImage


class ProductModelConstraintTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")

    def test_phone_number_defaults_to_placeholder(self):
        product = Product.objects.create(
            category=self.category,
            title="iPhone Default Phone",
            brand="Apple",
            model_name="Default",
            description="Used phone",
            condition_score=Decimal("8.0"),
            price_uah=Decimal("20000"),
        )

        self.assertEqual(product.phone_number, "000")

    def test_phone_number_must_be_three_digits(self):
        product = Product(
            category=self.category,
            title="iPhone Invalid Inventory Code",
            brand="Apple",
            model_name="Invalid",
            phone_number="12",
            description="Used phone",
            condition_score=Decimal("8.0"),
            price_uah=Decimal("20000"),
        )

        with self.assertRaises(ValidationError) as exc:
            product.full_clean()

        self.assertIn("phone_number", exc.exception.message_dict)

    def test_price_must_be_non_negative(self):
        product = Product(
            category=self.category,
            title="iPhone 12",
            brand="Apple",
            model_name="12",
            description="Used phone",
            condition_score=Decimal("8.0"),
            price_uah=Decimal("-1"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_saving_legacy_number_preserves_existing_normalization(self):
        product = Product.objects.create(
            category=self.category,
            title="Legacy phone",
            brand="Apple",
            model_name="13",
            description="Used phone",
            condition_score=Decimal("8.0"),
            price_uah=Decimal("20000"),
        )
        Product.objects.filter(pk=product.pk).update(phone_number="1234567890")
        product.refresh_from_db()
        product.price_uah = Decimal("19000")
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.phone_number, "000")
        product.phone_number = "12"
        with self.assertRaises(ValidationError):
            product.save()

    def test_condition_must_be_between_0_and_10(self):
        product = Product(
            category=self.category,
            title="iPhone 13",
            brand="Apple",
            model_name="13",
            description="Used phone",
            condition_score=Decimal("10.5"),
            price_uah=Decimal("25000"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()


class CatalogExperienceTests(TestCase):
    def setUp(self):
        self.phones = Category.objects.create(name="Phones", slug="phones")
        self.tablets = Category.objects.create(name="Tablets", slug="tablets")

        self.available_product = Product.objects.create(
            category=self.phones,
            title="iPhone 12",
            brand="Apple",
            model_name="A2403",
            description="Good condition",
            condition_score=Decimal("8.5"),
            price_uah=Decimal("18000.00"),
            is_available=True,
            is_active=True,
        )
        self.sold_product = Product.objects.create(
            category=self.tablets,
            title="Galaxy Tab S7",
            brand="Samsung",
            model_name="SM-T870",
            description="Sold unit",
            condition_score=Decimal("7.5"),
            price_uah=Decimal("14000.00"),
            is_available=False,
            is_active=True,
        )
        self.device_model = DeviceModel.objects.create(brand="Apple", name="A2403")
        DeviceModelSpec.objects.create(
            device_model=self.device_model,
            label="Display",
            value='6.1" OLED',
            position=1,
        )
        DeviceModelSpec.objects.create(
            device_model=self.device_model,
            label="Storage",
            value="128 GB",
            position=2,
        )
        self.unavailable_match = Product.objects.create(
            category=self.phones,
            title="iPhone Hidden",
            brand="Apple",
            model_name="Hidden",
            description="Should not appear in search suggestions",
            condition_score=Decimal("8.0"),
            price_uah=Decimal("17000.00"),
            is_available=False,
            is_active=True,
        )
        for idx in range(1, 8):
            Product.objects.create(
                category=self.phones,
                title=f"iPhone Suggest {idx}",
                brand="Apple",
                model_name=f"S{idx}",
                description="Suggestion candidate",
                condition_score=Decimal("8.0"),
                price_uah=Decimal("15000.00"),
                is_available=True,
                is_active=True,
            )

    def test_catalog_page_renders_cards_with_add_to_cart(self):
        response = self.client.get(reverse("catalog:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "add-cart")
        self.assertContains(response, "iPhone 12")

    def test_catalog_rejects_nonfinite_and_oversized_price_filters(self):
        for field in ("min_price", "max_price"):
            for value in ("Infinity", "-Infinity", "NaN", "sNaN", "1e1000000", "9" * 100):
                for htmx in (False, True):
                    with self.subTest(field=field, value=value, htmx=htmx):
                        response = self.client.get(reverse("catalog:list"), {field: value}, HTTP_HX_REQUEST=str(htmx).lower())
                        self.assertEqual(response.status_code, 200)
                        self.assertIn(field, response.context["form"].errors)
                        selected_key = "selected_min_price" if field == "min_price" else "selected_max_price"
                        fallback_key = "price_floor" if field == "min_price" else "price_ceiling"
                        self.assertEqual(response.context[selected_key], response.context[fallback_key])

    def test_catalog_filters_by_query_and_category(self):
        response = self.client.get(
            reverse("catalog:list"),
            {"q": "iphone", "category": "phones"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "iPhone 12")
        self.assertNotContains(response, "Galaxy Tab S7")

    def test_catalog_filters_by_multiple_brands(self):
        response = self.client.get(
            reverse("catalog:list"),
            {"brand": ["Apple", "Samsung"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "iPhone 12")
        self.assertContains(response, "Galaxy Tab S7")

    def test_catalog_sorting_by_price_desc(self):
        response = self.client.get(reverse("catalog:list"), {"sort": "price_desc"})
        self.assertEqual(response.status_code, 200)
        products = list(response.context["products"])
        prices = [product.price_uah for product in products]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_search_suggestions_returns_up_to_five_products(self):
        response = self.client.get(reverse("catalog:search_suggestions"), {"q": "iphone"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("items", payload)
        self.assertEqual(len(payload["items"]), 5)
        for item in payload["items"]:
            self.assertIn("title", item)
            self.assertIn("url", item)
            self.assertIn("price_uah", item)

    def test_search_suggestions_excludes_unavailable_products(self):
        response = self.client.get(reverse("catalog:search_suggestions"), {"q": "iphone"})
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["items"]]
        self.assertNotIn(self.unavailable_match.title, titles)

    def test_search_suggestions_requires_min_length(self):
        response = self.client.get(reverse("catalog:search_suggestions"), {"q": "a"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_catalog_htmx_returns_partial(self):
        response = self.client.get(
            reverse("catalog:list"),
            {"q": "iphone"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-results-head")
        self.assertNotContains(response, "<!doctype html>")

    def test_product_detail_redirects_to_canonical_slug(self):
        response = self.client.get(
            reverse("catalog:product_detail", kwargs={"pk": self.available_product.pk, "slug": "wrong"})
        )
        self.assertEqual(response.status_code, 301)
        self.assertIn("iphone-12", response.headers["Location"])

    def test_product_detail_shows_availability(self):
        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"pk": self.sold_product.pk, "slug": "galaxy-tab-s7"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-meta")
        self.assertContains(response, "Продано")
        self.assertContains(response, "stitch-detail-add-cart-slot")
        self.assertContains(response, "stitch-detail-add-cart")
        self.assertContains(response, f'action="{reverse("orders:buy_now")}"', count=1)
        self.assertContains(response, "Купити зараз", count=1)
        self.assertContains(response, f'hx-post="{reverse("orders:cart_add")}"', count=1)

    def test_product_detail_renders_model_specs_tab(self):
        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"pk": self.available_product.pk, "slug": "iphone-12"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-detail-back-link")
        self.assertContains(response, "data-catalog-link")
        self.assertContains(response, "data-detail-tabs")
        self.assertContains(response, "data-tab-trigger=\"description\"")
        self.assertContains(response, "data-tab-trigger=\"specs\"")
        self.assertContains(response, "Display")
        self.assertContains(response, "128 GB")

    def test_robots_txt_exposes_sitemap(self):
        response = self.client.get(reverse("robots_txt"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Disallow: /upravlinnia-mahazynom/")
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")

    def test_sitemap_lists_core_pages_and_available_products(self):
        response = self.client.get(reverse("sitemap"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("home"))
        self.assertContains(response, reverse("catalog:list"))
        self.assertContains(response, reverse("privacy_policy"))
        self.assertNotContains(response, "/catalog/iphone-bu/")
        self.assertContains(
            response,
            reverse("catalog:product_detail", kwargs={"pk": self.available_product.pk, "slug": "iphone-12"}),
        )
        self.assertNotContains(
            response,
            reverse("catalog:product_detail", kwargs={"pk": self.sold_product.pk, "slug": "galaxy-tab-s7"}),
        )

    def test_home_page_outputs_seo_metadata(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'content="index,follow"')
        self.assertContains(response, 'rel="canonical" href="http://testserver/"')
        self.assertContains(response, "QuickPhoneUA - перевірені вживані смартфони з реальними фото")

    def test_filtered_catalog_page_is_noindex(self):
        response = self.client.get(reverse("catalog:list"), {"q": "iphone"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'content="noindex,follow"')
        self.assertContains(response, 'rel="canonical" href="http://testserver/catalog/"')

    def test_catalog_page_uses_original_layout_without_extra_intro(self):
        response = self.client.get(reverse("catalog:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-catalog")
        self.assertContains(response, 'id="catalog-results"')
        self.assertNotContains(response, "QuickPhone каталог")

    def test_legacy_used_iphone_path_returns_404(self):
        response = self.client.get("/catalog/iphone-bu/")
        self.assertEqual(response.status_code, 404)

    def test_removed_integration_api_routes_return_404(self):
        for path in ("/api/catalog/categories/", "/api/catalog/products/", "/api/catalog/products/1/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_available_product_detail_is_indexable_and_sold_product_is_not(self):
        available_response = self.client.get(
            reverse("catalog:product_detail", kwargs={"pk": self.available_product.pk, "slug": "iphone-12"})
        )
        self.assertEqual(available_response.status_code, 200)
        self.assertContains(available_response, 'content="index,follow"')

        sold_response = self.client.get(
            reverse("catalog:product_detail", kwargs={"pk": self.sold_product.pk, "slug": "galaxy-tab-s7"})
        )
        self.assertEqual(sold_response.status_code, 200)
        self.assertContains(sold_response, 'content="noindex,follow"')

    def test_login_and_checkout_pages_are_noindex(self):
        login_response = self.client.get(reverse("users:login"))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'content="noindex,nofollow"')

        checkout_response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(checkout_response.status_code, 200)
        self.assertContains(checkout_response, 'content="noindex,nofollow"')

    def test_base_shell_loads_stitch_assets(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "css/stitch_mvp.css")
        self.assertContains(response, "js/ui.js")
        self.assertContains(response, "qp-performance-lite")

    def test_privacy_policy_page_uses_glass_layout(self):
        response = self.client.get(reverse("privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "privacy_policy.html")
        self.assertContains(response, "Політика конфіденційності")
        self.assertContains(response, "stitch-policy-content")
        self.assertContains(response, "qp-glass-section")

    def test_footer_contains_privacy_policy_link(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("privacy_policy"))
        self.assertNotContains(response, "/catalog/iphone-bu/")
        self.assertContains(response, "stitch-footer-link")
        self.assertContains(response, "stitch-footer-social-link")
        self.assertContains(response, f"tel:{settings.CONTACT_PHONE_E164}")
        self.assertContains(response, settings.CONTACT_MANAGER_TELEGRAM_URL)
        self.assertContains(response, settings.SOCIAL_INSTAGRAM_URL)
        self.assertContains(response, settings.SOCIAL_TELEGRAM_URL)
        self.assertContains(response, settings.SOCIAL_TIKTOK_URL)

    def test_layout_has_floating_manager_telegram_button(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-floating-contact")
        self.assertContains(response, "stitch-floating-manager")
        self.assertContains(response, "stitch-floating-manager--call")
        self.assertContains(response, settings.CONTACT_MANAGER_TELEGRAM_URL)
        self.assertContains(response, f"tel:{settings.CONTACT_PHONE_E164}")

    def test_header_catalog_dropdown_renders_categories_and_brands(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-catalog-menu")
        self.assertContains(response, "stitch-catalog-menu__panel")
        self.assertContains(response, "category=phones")
        self.assertContains(response, "brand=Apple")

    def test_home_page_prefers_admin_selected_carousel_products(self):
        chosen_late = Product.objects.create(
            category=self.phones,
            title="Chosen Late",
            brand="Apple",
            model_name="CL-1",
            description="Admin selected for homepage",
            condition_score=Decimal("9.0"),
            price_uah=Decimal("22000.00"),
            is_available=True,
            is_active=True,
            show_on_homepage_carousel=True,
            homepage_carousel_order=20,
        )
        chosen_early = Product.objects.create(
            category=self.phones,
            title="Chosen Early",
            brand="Apple",
            model_name="CE-1",
            description="Admin selected for homepage",
            condition_score=Decimal("9.0"),
            price_uah=Decimal("21000.00"),
            is_available=True,
            is_active=True,
            show_on_homepage_carousel=True,
            homepage_carousel_order=10,
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        carousel_titles = [product.title for product in response.context["home_carousel_products"]]
        self.assertEqual(carousel_titles[:2], [chosen_early.title, chosen_late.title])
        self.assertNotIn(self.available_product.title, carousel_titles)

    def test_home_page_falls_back_to_latest_available_products_when_no_admin_selection(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        carousel_titles = [product.title for product in response.context["home_carousel_products"]]
        self.assertIn(self.available_product.title, carousel_titles)
        self.assertNotIn(self.sold_product.title, carousel_titles)
        self.assertGreaterEqual(response.context["home_carousel_count"], 1)

    def test_home_and_catalog_have_stitch_markers(self):
        home = self.client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "home-hero")
        self.assertContains(home, "Перейти до каталогу")
        self.assertContains(home, "data-home-carousel")
        self.assertContains(home, "home_carousel.js")
        self.assertContains(home, "data-cart-open")
        self.assertContains(home, "stitch-cart-toggle__svg")
        self.assertContains(home, "qp-performance-lite")

        catalog = self.client.get(reverse("catalog:list"))
        self.assertEqual(catalog.status_code, 200)
        self.assertContains(catalog, "stitch-catalog")
        self.assertContains(catalog, "id=\"catalog-results\"")
        self.assertContains(catalog, "data-filter-open")
        self.assertContains(catalog, "qp-performance-lite")

    def test_active_filters_render_chip_remove_links(self):
        response = self.client.get(
            reverse("catalog:list"),
            {"q": "iphone", "brand": "Apple"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-active-filters")
        self.assertContains(response, "active-filter-chip")
        self.assertContains(response, "Пошук: iphone")

    def test_stitch_css_and_catalog_script_hooks_present(self):
        stitch_css = (Path(settings.BASE_DIR) / "static/css/stitch_mvp.css").read_text(encoding="utf-8")
        script = (Path(settings.BASE_DIR) / "static/js/catalog_filters.js").read_text(encoding="utf-8")
        self.assertIn(".stitch-hero", stitch_css)
        self.assertIn("@media", stitch_css)
        self.assertIn("data-catalog-header-search", script)
        self.assertIn("data-price-min-range", self.client.get(reverse("catalog:list")).content.decode("utf-8"))
        self.assertIn("data-sort-select", self.client.get(reverse("catalog:list")).content.decode("utf-8"))
        self.assertIn("data-filter-open", self.client.get(reverse("catalog:list")).content.decode("utf-8"))


class ProductAdminBulkImportTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="strong-pass-123",
        )
        self.client.force_login(self.admin_user)

    def test_product_changelist_exposes_bulk_import_link(self):
        response = self.client.get(reverse("admin:catalog_product_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("admin:catalog_product_bulk_import"))
        self.assertContains(response, "Масове додавання")

    def test_bulk_import_creates_products_from_pasted_table(self):
        payload = {
            "source_text": (
                "title\tbrand\tmodel_name\tphone_number\tprice_uah\tcondition_score\tbattery_health\n"
                "iPhone 13 128GB\tApple\t13\t123\t23500\t9.0\t87\n"
                "iPhone 12 64GB\tApple\t12\t\t17900\t8.4\t82\n"
            ),
            "default_category": str(self.category.pk),
            "description_template": "{title} з батареєю {battery_health}%.",
            "default_is_available": "on",
            "default_is_active": "on",
        }

        response = self.client.post(reverse("admin:catalog_product_bulk_import"), payload)

        self.assertRedirects(response, reverse("admin:catalog_product_changelist"))
        self.assertEqual(Product.objects.count(), 2)
        created_product = Product.objects.get(title="iPhone 13 128GB")
        self.assertEqual(created_product.category, self.category)
        self.assertEqual(created_product.phone_number, "123")
        self.assertEqual(created_product.description, "iPhone 13 128GB з батареєю 87%.")
        self.assertTrue(created_product.is_available)
        self.assertTrue(created_product.is_active)
        self.assertEqual(Product.objects.get(title="iPhone 12 64GB").phone_number, "000")

    def test_bulk_import_shows_row_errors_and_rolls_back_all_products(self):
        payload = {
            "source_text": (
                "title\tbrand\tmodel_name\tprice_uah\tcondition_score\n"
                "iPhone 13 128GB\tApple\t13\t23500\t9.0\n"
                "Broken Phone\tApple\tBroken\tabc\t8.0\n"
            ),
            "default_category": str(self.category.pk),
            "description_template": "{title} опис.",
            "default_is_available": "on",
            "default_is_active": "on",
        }

        response = self.client.post(reverse("admin:catalog_product_bulk_import"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Рядок 3")
        self.assertContains(response, "price_uah: некоректне число")
        self.assertContains(response, "abc")
        self.assertEqual(Product.objects.count(), 0)

    def test_bulk_import_reports_invalid_description_templates_without_creating_products(self):
        for template in ("{title.missing}", "{title[999]}", "{title[bad]}", "{title!bad}", "{title"):
            with self.subTest(template=template):
                response = self.client.post(
                    reverse("admin:catalog_product_bulk_import"),
                    {
                        "source_text": "title\tbrand\tmodel_name\tprice_uah\tcondition_score\nPhone\tApple\t13\t1000\t8.0",
                        "default_category": self.category.pk,
                        "description_template": template,
                        "default_is_available": "on",
                        "default_is_active": "on",
                    },
                )
                self.assertContains(response, "Шаблон опису містить помилку")
                self.assertEqual(Product.objects.count(), 0)


class ProductAdminMultiImageUploadTests(TestCase):
    GIF_BYTES = (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00"
        b"\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00"
        b"\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )

    def setUp(self):
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.admin_user = get_user_model().objects.create_superuser(
            username="media-admin",
            email="media-admin@example.com",
            password="strong-pass-123",
        )
        self.client.force_login(self.admin_user)
        self.temp_media = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()

    def test_admin_add_view_creates_multiple_product_images(self):
        payload = {
            "category": str(self.category.pk),
            "title": "iPhone 14 128GB",
            "brand": "Apple",
            "model_name": "14",
            "description": "Смартфон у хорошому стані.",
            "condition_score": "9.1",
            "price_uah": "28999.00",
            "battery_health": "88",
            "homepage_carousel_order": "0",
            "additional_images": [
                SimpleUploadedFile("front.gif", self.GIF_BYTES, content_type="image/gif"),
                SimpleUploadedFile("back.gif", self.GIF_BYTES, content_type="image/gif"),
            ],
            "is_available": "on",
            "is_active": "on",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }

        response = self.client.post(reverse("admin:catalog_product_add"), payload)

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(title="iPhone 14 128GB")
        self.assertEqual(product.phone_number, "000")
        self.assertEqual(ProductImage.objects.filter(product=product).count(), 2)
        images = list(ProductImage.objects.filter(product=product).order_by("position"))
        self.assertTrue(images[0].is_primary)
        self.assertFalse(images[1].is_primary)
        self.assertEqual(images[0].alt_text, product.title)
        self.assertEqual(images[1].alt_text, product.title)
