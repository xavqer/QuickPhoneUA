from datetime import timedelta
from decimal import Decimal
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem

from . import services
from .forms import PhoneRegistrationForm, ProfileUpdateForm
from .models import PhoneVerificationChallenge
from .sms_client import SmsClubClient
from .views import VERIFICATION_SESSION_KEYS


@override_settings(
    SMS_VERIFICATION_ENABLED=False,
    SMS_VERIFICATION_FAKE_DELIVERY=True,
    SMS_VERIFICATION_TEST_CODE="123456",
    SMS_LOGIN_REVERIFY_DAYS=30,
)
class PhoneAuthTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def _registration_payload(self, **overrides):
        payload = {
            "first_name": "Іван",
            "last_name": "Петренко",
            "phone": "050 123 45 67",
            "password1": "QpStrongPass123!",
            "password2": "QpStrongPass123!",
        }
        payload.update(overrides)
        return payload

    @override_settings(REGISTRATION_ENABLED=False)
    def test_disabled_demo_registration_blocks_get_and_post_with_or_without_sms(self):
        for sms_enabled in (False, True):
            with self.subTest(sms_enabled=sms_enabled), self.settings(SMS_VERIFICATION_ENABLED=sms_enabled):
                with patch("apps.users.services.SmsClubClient.send_sms") as send_sms:
                    responses = (
                        self.client.get(reverse("users:register")),
                        self.client.post(reverse("users:register"), self._registration_payload()),
                    )
                send_sms.assert_not_called()
                for response in responses:
                    self.assertContains(response, "Реєстрація недоступна", status_code=403)
                    self.assertContains(response, "сервіс SMS", status_code=403)
                    self.assertContains(response, f'href="{reverse("catalog:list")}"', status_code=403)
                    self.assertNotContains(response, 'name="phone"', status_code=403)
                    self.assertNotContains(response, 'name="password1"', status_code=403)
                    self.assertNotContains(response, 'name="code"', status_code=403)
                    self.assertTrue(response.context["registration_disabled"])
                self.assertEqual(self.user_model.objects.count(), 0)
                self.assertEqual(PhoneVerificationChallenge.objects.count(), 0)

    @override_settings(REGISTRATION_ENABLED=False, SMS_VERIFICATION_ENABLED=True)
    def test_disabled_demo_registration_cannot_confirm_pending_registration(self):
        challenge = services.start_registration_verification(self._registration_payload())
        session = self.client.session
        session[VERIFICATION_SESSION_KEYS[PhoneVerificationChallenge.Purpose.REGISTRATION]] = challenge.pk
        session.save()
        response = self.client.post(reverse("users:register"), {"verification_action": "verify", "code": "123456"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.user_model.objects.count(), 0)
        challenge.refresh_from_db()
        self.assertIsNone(challenge.consumed_at)
        self.assertNotContains(response, 'name="code"', status_code=403)

    @override_settings(REGISTRATION_ENABLED=False)
    def test_disabled_registration_preserves_authenticated_redirect(self):
        user = self.user_model.objects.create_user(username="existing-demo-user")
        self.client.force_login(user)
        response = self.client.get(reverse("users:register"), {"next": reverse("users:profile")})
        self.assertRedirects(response, reverse("users:profile"), fetch_redirect_response=False)

    def test_registration_normalizes_local_phone_and_logs_user_in(self):
        response = self.client.post(reverse("users:register"), self._registration_payload())

        self.assertRedirects(response, reverse("home"))
        user = self.user_model.objects.get()
        self.assertEqual(user.first_name, "Іван")
        self.assertEqual(user.last_name, "Петренко")
        self.assertEqual(user.phone, "+380501234567")
        self.assertEqual(user.username, "+380501234567")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_registration_requires_name_and_surname(self):
        response = self.client.post(
            reverse("users:register"),
            self._registration_payload(first_name="", last_name=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_model.objects.count(), 0)
        self.assertIn("first_name", response.context["form"].errors)
        self.assertIn("last_name", response.context["form"].errors)

    def test_registration_rejects_duplicate_phone(self):
        self.user_model.objects.create_user(
            username="+380501234567",
            phone="+380501234567",
            password="QpStrongPass123!",
        )
        response = self.client.post(
            reverse("users:register"),
            self._registration_payload(phone="0501234567"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user_model.objects.count(), 1)
        self.assertContains(response, "Користувач з цим номером уже існує.")

    def test_login_by_phone_supports_local_format_and_next_redirect(self):
        user = self.user_model.objects.create_user(
            username="+380501234567",
            phone="+380501234567",
            password="QpStrongPass123!",
        )
        response = self.client.post(
            reverse("users:login"),
            {
                "phone": "0501234567",
                "password": "QpStrongPass123!",
                "next": "/orders/checkout/",
            },
        )

        self.assertRedirects(response, "/orders/checkout/", fetch_redirect_response=False)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_login_rejects_invalid_ua_phone(self):
        response = self.client.post(
            reverse("users:login"),
            {
                "phone": "12345",
                "password": "anything",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+380XXXXXXXXX")

    def test_login_page_hides_password_reset_link_when_sms_disabled(self):
        response = self.client.get(reverse("users:login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Забули пароль?")

    def test_registration_ignores_external_next_url(self):
        response = self.client.post(
            reverse("users:register"),
            self._registration_payload(
                phone="0671234567",
                next="https://evil.example.com",
            ),
        )

        self.assertRedirects(response, reverse("home"))

    def test_registration_prefills_fields_from_query(self):
        response = self.client.get(
            reverse("users:register"),
            {
                "first_name": "Taras",
                "last_name": "Shevchenko",
                "phone": "+38 (050) 123 45 67",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'value="Taras"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'value="Shevchenko"')
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'value="+38 (050) 123 45 67"')

    def test_logout_requires_post_and_logs_user_out(self):
        user = self.user_model.objects.create_user(
            username="+380631234567",
            phone="+380631234567",
            password="QpStrongPass123!",
        )
        self.client.force_login(user)

        get_response = self.client.get(reverse("users:logout"))
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post(reverse("users:logout"))
        self.assertRedirects(post_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(
    SMS_VERIFICATION_ENABLED=False,
    SMS_VERIFICATION_FAKE_DELIVERY=True,
    SMS_VERIFICATION_TEST_CODE="123456",
)
class ProfileViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.user = self.user_model.objects.create_user(
            username="+380501112233",
            phone="+380501112233",
            first_name="Іван",
            last_name="Коваленко",
            password="QpStrongPass123!",
        )

    def test_profile_requires_login(self):
        profile_url = reverse("users:profile")
        login_url = reverse("users:login")

        response = self.client.get(profile_url)

        self.assertRedirects(
            response,
            f"{login_url}?next={profile_url}",
            fetch_redirect_response=False,
        )

    def test_profile_shows_only_current_user_orders(self):
        other_user = self.user_model.objects.create_user(
            username="+380671112233",
            phone="+380671112233",
            password="QpStrongPass123!",
        )
        category = Category.objects.create(name="Phones", slug="phones")
        visible_product = Product.objects.create(
            category=category,
            title="Visible Product",
            brand="Apple",
            model_name="A2403",
            description="Visible",
            condition_score=Decimal("8.5"),
            price_uah=Decimal("18000.00"),
            is_available=True,
            is_active=True,
        )
        hidden_product = Product.objects.create(
            category=category,
            title="Hidden Product",
            brand="Samsung",
            model_name="SM-G980",
            description="Hidden",
            condition_score=Decimal("7.1"),
            price_uah=Decimal("9000.00"),
            is_available=True,
            is_active=True,
        )

        visible_order = Order.objects.create(
            user=self.user,
            contact_name="Іван Коваленко",
            contact_phone="+380501112233",
        )
        OrderItem.objects.create(
            order=visible_order,
            product=visible_product,
            quantity=2,
            price_at_order=Decimal("17000.00"),
        )
        hidden_order = Order.objects.create(
            user=other_user,
            contact_name="Інший Клієнт",
            contact_phone="+380671112233",
        )
        OrderItem.objects.create(
            order=hidden_order,
            product=hidden_product,
            quantity=1,
            price_at_order=Decimal("8800.00"),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Профіль")
        self.assertContains(response, "Замовлення")
        self.assertContains(response, f"Замовлення #{visible_order.id}")
        self.assertContains(response, "Visible Product")
        self.assertNotContains(response, f"Замовлення #{hidden_order.id}")
        self.assertNotContains(response, "Hidden Product")

    def test_profile_displays_order_status_in_ukrainian(self):
        Order.objects.create(
            user=self.user,
            contact_name="Test User",
            contact_phone="+380501112233",
            status=Order.Status.PENDING_REVIEW,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Очікує підтвердження")
        self.assertNotContains(response, "Pending review")

    def test_nav_profile_menu_does_not_contain_profile_shortcut(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-profile-menu-panel")
        self.assertNotContains(response, "stitch-profile-menu__item--profile")

    def test_nav_profile_menu_has_profile_target_for_desktop_click(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-profile-url="')
        self.assertContains(response, reverse("users:profile"))

    def test_profile_default_mode_hides_edit_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{reverse('users:profile')}?edit=1")
        self.assertNotContains(response, 'id="profile-edit-form"')
        self.assertNotContains(response, "data-profile-confirm-open")

    def test_profile_page_contains_logout_button_and_hides_change_phone_shortcut(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'action="{reverse("users:logout")}"')
        self.assertNotContains(response, reverse("users:phone_change_request"))
        self.assertContains(response, "Вийти")

    def test_profile_edit_mode_shows_form_and_custom_confirmation_dialog(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"), {"edit": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="profile-edit-form"')
        self.assertContains(response, "data-profile-confirm-open")
        self.assertContains(response, "data-profile-confirm")
        self.assertContains(response, "Застосувати зміни профілю?")

    def test_profile_update_applies_changes_and_sets_success_flag(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("users:profile"),
            {
                "last_name": "Вовк",
                "first_name": "Наталія",
                "telegram_handle": "@nataliia_qp",
            },
        )

        self.assertRedirects(response, f"{reverse('users:profile')}?updated=1")
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Вовк")
        self.assertEqual(self.user.first_name, "Наталія")
        self.assertEqual(self.user.telegram_handle, "@nataliia_qp")

        success_page = self.client.get(reverse("users:profile"), {"updated": "1"})
        self.assertContains(success_page, "Дані профілю оновлено.")

    def test_profile_displays_phone_in_formatted_style(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "+38 (050) 111 22 33")


@override_settings(
    SMS_VERIFICATION_ENABLED=True,
    SMS_VERIFICATION_FAKE_DELIVERY=True,
    SMS_VERIFICATION_TEST_CODE="123456",
    SMS_LOGIN_REVERIFY_DAYS=30,
)
class SmsVerificationFeatureTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def test_confirmation_rejects_wrong_purpose_before_checking_code(self):
        challenge = PhoneVerificationChallenge(purpose="unexpected")
        calls = (
            (services.confirm_registration, (challenge, "123456")),
            (services.confirm_login_verification, (challenge, "123456")),
            (services.confirm_password_reset, (challenge, "123456", "new-password")),
            (services.confirm_phone_change, (challenge, "123456")),
        )
        for confirm, args in calls:
            with self.subTest(action=confirm.__name__):
                with self.assertRaisesMessage(services.PhoneVerificationError, "Некоректний тип підтвердження."):
                    confirm(*args)

    def test_code_generation_preserves_configured_length_and_test_override(self):
        for length, expected in ((3, 4), (6, 6), (8, 8)):
            with self.subTest(length=length), self.settings(
                SMS_VERIFICATION_TEST_CODE="", SMS_VERIFICATION_CODE_LENGTH=length
            ):
                code = services.generate_verification_code()
                self.assertEqual(len(code), expected)
                self.assertTrue(code.isascii() and code.isdigit())
        with self.settings(SMS_VERIFICATION_TEST_CODE=" 987 "):
            self.assertEqual(services.generate_verification_code(), "987")

    def test_failed_attempts_persist_and_stale_objects_cannot_bypass_lockout(self):
        calls = {
            PhoneVerificationChallenge.Purpose.REGISTRATION: services.confirm_registration,
            PhoneVerificationChallenge.Purpose.LOGIN: services.confirm_login_verification,
            PhoneVerificationChallenge.Purpose.PASSWORD_RESET: services.confirm_password_reset,
            PhoneVerificationChallenge.Purpose.PHONE_CHANGE: services.confirm_phone_change,
        }
        for purpose, confirm in calls.items():
            with self.subTest(purpose=purpose):
                challenge = PhoneVerificationChallenge(
                    purpose=purpose, phone="+380671234567", max_attempts=2,
                    expires_at=timezone.now() + timedelta(minutes=10),
                )
                challenge.set_code("123456")
                challenge.save()
                stale = PhoneVerificationChallenge.objects.get(pk=challenge.pk)
                extra = ("NewPassword123!",) if purpose == PhoneVerificationChallenge.Purpose.PASSWORD_RESET else ()
                for attempts in (1, 2):
                    with self.assertRaises(services.PhoneVerificationError):
                        confirm(stale, "000000", *extra)
                    challenge.refresh_from_db()
                    self.assertEqual(challenge.attempts_count, attempts)
                # Test the limit independently of the expiration side effect.
                PhoneVerificationChallenge.objects.filter(pk=challenge.pk).update(
                    expires_at=timezone.now() + timedelta(minutes=10)
                )
                with self.assertRaisesMessage(services.PhoneVerificationError, "Ліміт спроб"):
                    confirm(stale, "123456", *extra)
                challenge.refresh_from_db()
                self.assertEqual(challenge.attempts_count, 2)
                self.assertIsNone(challenge.consumed_at)

    def test_stale_consumed_challenge_cannot_be_reused(self):
        user = self.user_model.objects.create_user(username="login-test", phone="+380671234567")
        challenge = services.start_login_verification(user)
        stale = PhoneVerificationChallenge.objects.get(pk=challenge.pk)
        services.confirm_login_verification(challenge, "123456")
        with self.assertRaisesMessage(services.PhoneVerificationError, "уже використано"):
            services.confirm_login_verification(stale, "123456")

    def test_account_changes_roll_back_when_consuming_code_fails(self):
        user = self.user_model.objects.create_user(
            username="rollback-test", phone="+380671234567", password="OldPassword123!"
        )
        for purpose in (PhoneVerificationChallenge.Purpose.REGISTRATION,
                        PhoneVerificationChallenge.Purpose.PASSWORD_RESET,
                        PhoneVerificationChallenge.Purpose.PHONE_CHANGE):
            with self.subTest(purpose=purpose):
                if purpose == PhoneVerificationChallenge.Purpose.REGISTRATION:
                    challenge = services.start_registration_verification(self._registration_payload())
                    confirm = services.confirm_registration
                    extra = ()
                elif purpose == PhoneVerificationChallenge.Purpose.PASSWORD_RESET:
                    challenge = services.start_password_reset_verification(user)
                    confirm = services.confirm_password_reset
                    extra = ("NewPassword123!",)
                else:
                    challenge = services.start_phone_change_verification(user, "+380501112233")
                    confirm = services.confirm_phone_change
                    extra = ()
                with patch.object(PhoneVerificationChallenge, "consume", side_effect=RuntimeError("consume failed")):
                    with self.assertRaisesMessage(RuntimeError, "consume failed"):
                        confirm(challenge, "123456", *extra)
                challenge.refresh_from_db()
                user.refresh_from_db()
                self.assertIsNone(challenge.consumed_at)
                self.assertEqual(self.user_model.objects.count(), 1)
                self.assertEqual(user.phone, "+380671234567")
                self.assertEqual(user.username, "rollback-test")
                self.assertTrue(user.check_password("OldPassword123!"))

    def test_fake_sms_prints_code_locally_without_contacting_provider(self):
        for debug in (True, False):
            with self.subTest(debug=debug), self.settings(DEBUG=debug):
                output = StringIO()
                with patch("apps.users.sms_client.urlopen") as send, redirect_stdout(output):
                    result = SmsClubClient(fake_delivery=True).send_sms(
                        "+380000000000", "DEMO code: 123456"
                    )
                send.assert_not_called()
                self.assertTrue(result["ok"])
                self.assertTrue(result["message_id"].startswith("fake-"))
                if debug:
                    self.assertIn("+380000000000", output.getvalue())
                    self.assertIn("DEMO code: 123456", output.getvalue())
                else:
                    self.assertEqual(output.getvalue(), "")

    def test_sms_response_shapes_return_structured_errors(self):
        client = SmsClubClient()
        for body in ("[]", "null", "42", '"text"', '{"success_request":[1]}',
                     '{"success_request":42}', '{"success_request":{"info":[1]}}',
                     '{"success_request":{"add_info":[1]}}', "invalid JSON"):
            with self.subTest(body=body):
                result = client._parse_response(body, "Invalid SMS response")
                self.assertFalse(result["ok"])
                self.assertEqual(result["message"], "Invalid SMS response")
                self.assertEqual(result["message_id"], "")
        self.assertEqual(client._parse_response(
            '{"success_request":{"info":{"123":"sent"}}}', "fallback"
        )["message_id"], "123")
        self.assertEqual(client._parse_response(
            '{"success_request":{"add_info":{"error":"rejected"}}}', "fallback"
        )["message"], "rejected")

    def _registration_payload(self, **overrides):
        payload = {
            "first_name": "Іван",
            "last_name": "Петренко",
            "phone": "050 123 45 67",
            "password1": "QpStrongPass123!",
            "password2": "QpStrongPass123!",
        }
        payload.update(overrides)
        return payload

    def test_registration_requires_sms_verification_when_enabled(self):
        response = self.client.post(reverse("users:register"), self._registration_payload())

        self.assertRedirects(response, reverse("users:register"), fetch_redirect_response=False)
        self.assertEqual(self.user_model.objects.count(), 0)

        overlay_page = self.client.get(reverse("users:register"))
        self.assertContains(overlay_page, "Підтвердіть номер телефону")

        verify_response = self.client.post(
            reverse("users:register"),
            {
                "verification_action": "verify",
                "code": "123456",
            },
        )

        self.assertRedirects(verify_response, reverse("home"))
        user = self.user_model.objects.get()
        self.assertEqual(user.phone, "+380501234567")
        self.assertIsNotNone(user.phone_verified_at)

    def test_login_requires_sms_after_long_absence_when_enabled(self):
        user = self.user_model.objects.create_user(
            username="+380501234567",
            phone="+380501234567",
            password="QpStrongPass123!",
        )
        user.last_login = timezone.now() - timedelta(days=45)
        user.save(update_fields=["last_login"])

        response = self.client.post(
            reverse("users:login"),
            {
                "phone": "0501234567",
                "password": "QpStrongPass123!",
                "next": "/orders/checkout/",
            },
        )

        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)
        overlay_page = self.client.get(reverse("users:login"))
        self.assertContains(overlay_page, "Підтвердіть вхід кодом")

        verify_response = self.client.post(
            reverse("users:login"),
            {
                "verification_action": "verify",
                "code": "123456",
            },
        )

        self.assertRedirects(verify_response, "/orders/checkout/", fetch_redirect_response=False)

    def test_password_reset_overlay_updates_password_when_enabled(self):
        user = self.user_model.objects.create_user(
            username="+380631234567",
            phone="+380631234567",
            password="OldPass123!",
        )

        response = self.client.post(
            reverse("users:password_reset_request"),
            {"phone": "0631234567"},
        )

        self.assertRedirects(response, reverse("users:password_reset_request"), fetch_redirect_response=False)
        overlay_page = self.client.get(reverse("users:password_reset_request"))
        self.assertContains(overlay_page, "Встановіть новий пароль")

        confirm_response = self.client.post(
            reverse("users:password_reset_request"),
            {
                "verification_action": "verify",
                "code": "123456",
                "password1": "QpStrongPass456!",
                "password2": "QpStrongPass456!",
            },
        )

        self.assertRedirects(confirm_response, f"{reverse('users:profile')}?password_reset=1")
        user.refresh_from_db()
        self.assertTrue(user.check_password("QpStrongPass456!"))

    def test_phone_change_flow_updates_phone_when_enabled(self):
        user = self.user_model.objects.create_user(
            username="+380501112233",
            phone="+380501112233",
            password="QpStrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("users:phone_change_request"),
            {"phone": "0671234567"},
        )

        self.assertRedirects(response, reverse("users:phone_change_request"), fetch_redirect_response=False)
        overlay_page = self.client.get(reverse("users:phone_change_request"))
        self.assertContains(overlay_page, "Підтвердіть новий номер телефону")

        verify_response = self.client.post(
            reverse("users:phone_change_request"),
            {
                "verification_action": "verify",
                "code": "123456",
            },
        )

        self.assertRedirects(verify_response, f"{reverse('users:profile')}?phone_changed=1")
        user.refresh_from_db()
        self.assertEqual(user.phone, "+380671234567")
        self.assertEqual(user.username, "+380671234567")


@override_settings(
    SMS_VERIFICATION_ENABLED=True,
    SMS_VERIFICATION_FAKE_DELIVERY=True,
    SMS_VERIFICATION_TEST_CODE="123456",
    SMS_VERIFICATION_RESEND_SECONDS=0,
)
class VerificationResendTests(TestCase):
    routes = {
        PhoneVerificationChallenge.Purpose.REGISTRATION: "users:register",
        PhoneVerificationChallenge.Purpose.LOGIN: "users:login",
        PhoneVerificationChallenge.Purpose.PASSWORD_RESET: "users:password_reset_request",
        PhoneVerificationChallenge.Purpose.PHONE_CHANGE: "users:phone_change_request",
    }

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="+380501234567", phone="+380501234567"
        )

    def prepare_challenge(self, purpose):
        self.client = Client()
        if purpose == PhoneVerificationChallenge.Purpose.PHONE_CHANGE:
            self.client.force_login(self.user)
        challenge = PhoneVerificationChallenge.objects.create(
            purpose=purpose,
            phone="+380671234567",
            user=None if purpose == PhoneVerificationChallenge.Purpose.REGISTRATION else self.user,
            payload={"next_url": "/orders/checkout/"},
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        session = self.client.session
        session[VERIFICATION_SESSION_KEYS[purpose]] = challenge.pk
        session.save()
        return challenge

    def test_resend_replaces_challenge_for_every_overlay(self):
        for purpose, route in self.routes.items():
            with self.subTest(purpose=purpose):
                original = self.prepare_challenge(purpose)
                response = self.client.post(reverse(route), {"verification_action": "resend"})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["verification"]["resend_success"])
                replacement_id = self.client.session[VERIFICATION_SESSION_KEYS[purpose]]
                self.assertNotEqual(replacement_id, original.pk)
                replacement = PhoneVerificationChallenge.objects.get(pk=replacement_id)
                self.assertEqual(replacement.purpose, purpose)
                self.assertEqual(replacement.payload, original.payload)
                self.assertEqual(replacement.user_id, original.user_id)
                self.assertTrue(replacement.check_code("123456"))
                original.refresh_from_db()
                self.assertTrue(original.is_expired)

    @override_settings(SMS_VERIFICATION_RESEND_SECONDS=60)
    def test_resend_cooldown_shows_errors_for_every_overlay(self):
        for purpose, route in self.routes.items():
            with self.subTest(purpose=purpose):
                original = self.prepare_challenge(purpose)
                response = self.client.post(reverse(route), {"verification_action": "resend"})
                self.assertEqual(response.status_code, 200)
                overlay = response.context["verification"]
                self.assertFalse(overlay["resend_success"])
                self.assertTrue(overlay["form"].non_field_errors())
                self.assertGreater(overlay["resend_wait_seconds"], 0)
                self.assertEqual(self.client.session[VERIFICATION_SESSION_KEYS[purpose]], original.pk)
                original.refresh_from_db()
                self.assertFalse(original.is_expired)

    @patch("apps.users.services.SmsClubClient.send_sms")
    def test_resend_delivery_errors_are_shown_for_every_overlay(self, send_sms):
        send_sms.return_value = {"ok": False, "message": "SMS unavailable"}
        for purpose, route in self.routes.items():
            with self.subTest(purpose=purpose):
                original = self.prepare_challenge(purpose)
                response = self.client.post(reverse(route), {"verification_action": "resend"})
                self.assertEqual(response.status_code, 200)
                overlay = response.context["verification"]
                self.assertFalse(overlay["resend_success"])
                self.assertEqual(list(overlay["form"].non_field_errors()), ["SMS unavailable"])
                self.assertEqual(self.client.session[VERIFICATION_SESSION_KEYS[purpose]], original.pk)


class UserFormContractTests(TestCase):
    def test_registration_commit_false_keeps_cleaned_fields_and_hashed_password(self):
        form = PhoneRegistrationForm(data={
            "first_name": "  Taras  ",
            "last_name": "  Shevchenko  ",
            "phone": "050 123 45 67",
            "password1": "QpStrongPass123!",
            "password2": "QpStrongPass123!",
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertEqual(user.first_name, "Taras")
        self.assertEqual(user.last_name, "Shevchenko")
        self.assertEqual(user.phone, "+380501234567")
        self.assertEqual(user.username, user.phone)
        self.assertIsNone(user.phone_verified_at)
        self.assertTrue(user.check_password("QpStrongPass123!"))
        self.assertEqual(get_user_model().objects.count(), 0)
        user.save()
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_profile_fields_keep_default_whitespace_cleaning(self):
        user = get_user_model().objects.create_user(username="test")
        form = ProfileUpdateForm(data={
            "first_name": "  Taras  ", "last_name": "  ", "telegram_handle": "  @taras  "
        }, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.first_name, "Taras")
        self.assertEqual(user.last_name, "")
        self.assertEqual(user.telegram_handle, "@taras")
