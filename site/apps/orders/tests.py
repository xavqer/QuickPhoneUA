from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.catalog.models import Category, Product
from apps.orders.cart import SESSION_KEY
from apps.orders.models import Order, OrderItem


class CartAndCheckoutTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Phones", slug="phones")
        self.available = Product.objects.create(
            category=category,
            title="iPhone 12",
            brand="Apple",
            model_name="A2403",
            description="Good",
            condition_score=Decimal("8.5"),
            price_uah=Decimal("18000.00"),
            is_available=True,
            is_active=True,
        )
        self.unavailable = Product.objects.create(
            category=category,
            title="Galaxy S20",
            brand="Samsung",
            model_name="SM-G980",
            description="Sold",
            condition_score=Decimal("7.0"),
            price_uah=Decimal("9000.00"),
            is_available=False,
            is_active=True,
        )

    def test_add_to_cart_updates_badge_count(self):
        response = self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        self.assertEqual(response.status_code, 200)
        badge = self.client.get(reverse("orders:cart_badge"))
        self.assertContains(badge, ">1<")

    def test_cart_actions_reject_invalid_product_ids_without_changing_cart(self):
        session = self.client.session
        session[SESSION_KEY] = [self.available.id]
        session.save()
        for action in ("cart_add", "buy_now", "cart_remove", "checkout_remove"):
            for value in (None, "", "abc", "1.5", "0", "-1", str(2**63), "9" * 100):
                with self.subTest(action=action, value=value):
                    payload = {} if value is None else {"product_id": value}
                    response = self.client.post(reverse(f"orders:{action}"), payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(self.client.session[SESSION_KEY], [self.available.id])
        self.assertFalse(Order.objects.exists())

    def test_cart_updates_mark_only_replacement_fragments_as_out_of_band(self):
        response = self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        self.assertContains(response, 'id="cart-badge" hx-swap-oob="true"')
        self.assertContains(response, 'id="cart-panel" hx-swap-oob="true"')
        self.assertNotContains(self.client.get(reverse("orders:cart_panel")), "hx-swap-oob")
        self.assertNotContains(self.client.get(reverse("orders:cart_badge")), "hx-swap-oob")

    def test_buy_now_redirects_to_checkout_and_adds_product(self):
        response = self.client.post(reverse("orders:buy_now"), {"product_id": self.available.id})
        self.assertRedirects(response, reverse("orders:checkout"), fetch_redirect_response=False)
        self.assertEqual(self.client.session.get(SESSION_KEY, []), [self.available.id])

    def test_guest_home_page_sets_csrf_cookie_for_cart_actions(self):
        csrf_client = Client(enforce_csrf_checks=True)
        home = csrf_client.get(reverse("home"))
        self.assertEqual(home.status_code, 200)
        self.assertIn("csrftoken", home.cookies)

        token = home.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("orders:cart_add"),
            {"product_id": self.available.id},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_checkout_page_sets_csrf_cookie_for_submit(self):
        csrf_client = Client(enforce_csrf_checks=True)
        session = csrf_client.session
        session[SESSION_KEY] = [self.available.id]
        session.save()

        checkout = csrf_client.get(reverse("orders:checkout"))
        self.assertEqual(checkout.status_code, 200)
        self.assertIn("csrftoken", checkout.cookies)

        token = checkout.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("orders:checkout_submit"),
            {
                "delivery_method": "pickup",
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "",
                "np_city_ref": "",
                "np_warehouse_name": "",
                "np_warehouse_ref": "",
            },
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

    def test_add_unavailable_product_is_blocked(self):
        response = self.client.post(reverse("orders:cart_add"), {"product_id": self.unavailable.id})
        self.assertEqual(response.status_code, 409)
        self.assertIn("stitch-feedback--error", response.content.decode("utf-8"))

    def test_add_existing_product_uses_info_feedback(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("stitch-feedback--info", response.content.decode("utf-8"))

    def test_checkout_has_remove_action_for_each_item(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'hx-post="{reverse("orders:checkout_remove")}"')

    def test_checkout_prefills_contact_fields_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="+380501234111",
            password="strong-pass-123",
            first_name="Іван",
            last_name="Петренко",
            phone="+380501234111",
            telegram_handle="@ivan_petrenko",
        )
        self.client.force_login(user)
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('name="contact_last_name"', html)
        self.assertIn('value="Петренко"', html)
        self.assertIn('name="contact_first_name"', html)
        self.assertIn('value="Іван"', html)
        self.assertIn('name="contact_phone"', html)
        self.assertIn('value="+38 (050) 123 41 11"', html)
        self.assertIn('name="contact_telegram"', html)
        self.assertIn('value="@ivan_petrenko"', html)

    def test_checkout_shows_login_link_for_guest(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.get(reverse("orders:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Вже маєте акаунт?")
        self.assertContains(response, f'{reverse("users:login")}?next={reverse("orders:checkout")}')

    def test_checkout_hides_login_link_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username="+380501239999",
            password="strong-pass-123",
            phone="+380501239999",
        )
        self.client.force_login(user)
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Вже маєте акаунт?")

    def test_checkout_accepts_display_phone_format_and_saves_normalized(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.latest("id")
        self.assertEqual(order.contact_phone, "+380501234567")

    def test_checkout_requires_middle_name(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Заповніть поле «По батькові».", status_code=400)

    def test_checkout_allows_manual_np_values_without_refs(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Київ",
                "np_city_ref": "",
                "np_warehouse_name": "Відділення №1",
                "np_warehouse_ref": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        order = Order.objects.latest("id")
        self.assertEqual(order.np_city_name, "Київ")
        self.assertEqual(order.np_city_ref, "")
        self.assertEqual(order.np_warehouse_name, "Відділення №1")
        self.assertEqual(order.np_warehouse_ref, "")

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_checkout_pickup_has_no_delivery_and_no_commission(self, estimate_mock):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "delivery_method": "pickup",
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "",
                "np_city_ref": "",
                "np_warehouse_name": "",
                "np_warehouse_ref": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        estimate_mock.assert_not_called()

        order = Order.objects.latest("id")
        self.assertEqual(order.delivery_method, Order.DeliveryMethod.PICKUP)
        self.assertEqual(order.np_city_name, "")
        self.assertEqual(order.np_warehouse_name, "")
        self.assertIsNone(order.delivery_cost_estimate)

        html = response.content.decode("utf-8")
        self.assertIn("Самовивіз", html)
        self.assertNotIn("<strong>Комісія:</strong>", html)
        self.assertNotIn("Орієнтовна вартість доставки", html)
        self.assertIn("До сплати", html)
        self.assertIn("18 000", html)

    def test_checkout_remove_updates_checkout_and_cart_fragments(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.post(reverse("orders:checkout_remove"), {"product_id": self.available.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get(SESSION_KEY, []), [])
        html = response.content.decode("utf-8")
        self.assertIn('id="cart-badge" hx-swap-oob="true"', html)
        self.assertIn('id="cart-panel" hx-swap-oob="true"', html)
        self.assertIn('id="checkout-content"', html)

    def test_checkout_rejects_invalid_phone_format(self):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "0501234567",
                "contact_telegram": "",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("+380XXXXXXXXX", response.content.decode("utf-8"))

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_checkout_creates_order_and_clears_cart(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "data": {"min": 120, "max": 170}}
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Шевченко",
                "contact_first_name": "Тарас",
                "contact_middle_name": "Григорович",
                "contact_phone": "+380501234567",
                "contact_telegram": "@buyer_ua",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)
        self.assertEqual(order.contact_name, "Шевченко Тарас Григорович")
        self.assertEqual(order.np_city_ref, "city-ref")
        self.assertEqual(order.np_warehouse_ref, "warehouse-ref")
        self.assertEqual(order.np_city_name, "Kyiv")
        self.assertEqual(order.np_warehouse_name, "Warehouse 1")
        self.assertEqual(order.delivery_cost_estimate, Decimal("170"))
        self.assertEqual(OrderItem.objects.first().price_at_order, self.available.price_uah)
        self.assertEqual(self.client.session.get(SESSION_KEY, []), [])

    @patch("apps.orders.views.OrderItem.objects.bulk_create", side_effect=RuntimeError("Item write failed"))
    def test_checkout_rolls_back_order_and_keeps_cart_when_item_save_fails(self, create_items):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        with self.assertRaisesMessage(RuntimeError, "Item write failed"):
            self.client.post(reverse("orders:checkout_submit"), {
                "delivery_method": "pickup",
                "contact_last_name": "Test",
                "contact_first_name": "Buyer",
                "contact_middle_name": "Name",
                "contact_phone": "+380501234567",
            })
        self.assertFalse(Order.objects.exists())
        self.assertFalse(OrderItem.objects.exists())
        self.assertEqual(self.client.session[SESSION_KEY], [self.available.id])

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_checkout_success_shows_guest_registration_cta_with_prefill(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "data": {"min": 120, "max": 170}}
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Shevchenko",
                "contact_first_name": "Taras",
                "contact_middle_name": "Hryhorovych",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Створити акаунт за 20 секунд")
        expected_url = f"{reverse('users:register')}?{urlencode({'last_name': 'Shevchenko', 'first_name': 'Taras', 'next': reverse('users:profile')})}"
        self.assertContains(response, expected_url.replace("&", "&amp;"))

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_checkout_success_hides_guest_registration_cta_for_authenticated_user(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "data": {"min": 120, "max": 170}}
        user = get_user_model().objects.create_user(
            username="+380501237777",
            password="strong-pass-123",
            phone="+380501237777",
        )
        self.client.force_login(user)
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Shevchenko",
                "contact_first_name": "Taras",
                "contact_middle_name": "Hryhorovych",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Kyiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Створити акаунт за 20 секунд")

    def test_order_default_status_pending_review(self):
        order = Order.objects.create(contact_name="A B", contact_phone="+380501234567")
        self.assertEqual(order.status, Order.Status.PENDING_REVIEW)
        self.assertEqual(order.delivery_method, Order.DeliveryMethod.NOVA_POSHTA)

    @patch("apps.orders.views.NovaPoshtaService.search_cities")
    def test_city_search_endpoint_returns_results(self, search_mock):
        search_mock.return_value = {"ok": True, "error_type": None, "message": "", "data": [{"name": "Kyiv", "ref": "ref1"}]}
        response = self.client.get(reverse("orders:np_city_search"), {"q": "ky"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kyiv", response.content.decode("utf-8"))

    @patch("apps.orders.views.NovaPoshtaService.get_warehouses")
    def test_warehouses_endpoint_handles_timeout(self, wh_mock):
        wh_mock.return_value = {"ok": False, "error_type": "timeout", "message": "timeout", "data": []}
        response = self.client.get(reverse("orders:np_warehouses"), {"city_ref": "ref1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("stitch-error", response.content.decode("utf-8"))
        self.assertIn("hx-get=\"/orders/np/warehouses/?city_ref=ref1\"", response.content.decode("utf-8"))

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_np_estimate_endpoint_renders_cost_block(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "error_type": None, "message": "", "data": {"min": Decimal("88.50"), "max": Decimal("88.50")}}
        response = self.client.get(reverse("orders:np_estimate"), {"city_ref": "ref1", "warehouse_ref": "wh1"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('id="checkout-delivery-value"', html)
        self.assertIn('id="checkout-total-value"', html)
        self.assertIn('hx-swap-oob="true"', html)
        self.assertIn('name="np_estimate_max" value="88,50"', html)

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_np_estimate_uses_current_cart_total_as_declared_cost(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "error_type": None, "message": "", "data": {"min": Decimal("88.50"), "max": Decimal("88.50")}}
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.get(reverse("orders:np_estimate"), {"city_ref": "ref1", "warehouse_ref": "wh1"})
        self.assertEqual(response.status_code, 200)

        _, kwargs = estimate_mock.call_args
        self.assertEqual(kwargs["declared_cost_uah"], Decimal("18000.00"))

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_np_estimate_replacements_keep_pickup_totals_for_all_results(self, estimate_mock):
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        for estimate in (
            {"ok": True, "data": {"min": Decimal("100"), "max": Decimal("100")}},
            {"ok": True, "data": {"min": Decimal("80"), "max": Decimal("100")}},
            {"ok": False, "message": "Delivery unavailable"},
        ):
            with self.subTest(estimate=estimate):
                estimate_mock.return_value = estimate
                response = self.client.get(reverse("orders:np_estimate"), {"city_ref": "ref1", "warehouse_ref": "wh1"})
                self.assertContains(response, 'data-pickup-text="Самовивіз"')
                self.assertContains(response, 'data-pickup-text="18 000 грн"')

    @patch("apps.orders.views.NovaPoshtaService.estimate_delivery_range")
    def test_checkout_success_shows_commission_field_and_total(self, estimate_mock):
        estimate_mock.return_value = {"ok": True, "data": {"min": Decimal("100.00"), "max": Decimal("100.00")}}
        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})

        response = self.client.post(
            reverse("orders:checkout_submit"),
            {
                "contact_last_name": "Shevchenko",
                "contact_first_name": "Taras",
                "contact_middle_name": "Hryhorovych",
                "contact_phone": "+38 (050) 123 45 67",
                "contact_telegram": "",
                "np_city_name": "Kharkiv",
                "np_city_ref": "city-ref",
                "np_warehouse_name": "Warehouse 1",
                "np_warehouse_ref": "warehouse-ref",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("Комісія", html)
        self.assertIn("До сплати", html)
        self.assertIn("18 480", html)

    def test_checkout_shell_uses_stitch_layout(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "stitch-header")
        self.assertContains(response, "stitch-btn")
        self.assertContains(response, "stitch-checkout")

    def test_checkout_and_cart_text_readability(self):
        cart = self.client.get(reverse("orders:cart_panel"))
        self.assertEqual(cart.status_code, 200)
        self.assertContains(cart, "Кошик")

        self.client.post(reverse("orders:cart_add"), {"product_id": self.available.id})
        checkout = self.client.get(reverse("orders:checkout"))
        self.assertEqual(checkout.status_code, 200)
        self.assertContains(checkout, "Оформлення замовлення")
        self.assertContains(checkout, "Контактні дані")
        self.assertContains(checkout, "Спосіб отримання")
        self.assertContains(checkout, "Самовивіз")
        self.assertContains(checkout, "Прізвище")
        self.assertContains(checkout, "По батькові")
        self.assertContains(checkout, "name=\"contact_first_name\"")
        self.assertContains(checkout, settings.CONTACT_MANAGER_TELEGRAM_URL)
        self.assertContains(checkout, f"tel:{settings.CONTACT_PHONE_E164}")

    def test_stitch_ui_script_has_expected_hooks(self):
        script = (Path(settings.BASE_DIR) / "static/js/ui.js").read_text(encoding="utf-8")
        self.assertIn("htmx:configRequest", script)
        self.assertIn("data-cart-open", script)
        self.assertIn("is-open", script)
